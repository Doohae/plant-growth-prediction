import torch
from torch.utils.data import DataLoader
import pandas as pd
import numpy as np
from tqdm.auto import tqdm
from dataloader import KistDataset
import os
from glob import glob
from model import CompareNet
import argparse


# Inference Part
def inference(model, test_data_loader, device, idx):
    test_value = []
    description = f"Fold-{idx}"
    with torch.no_grad():
        model.eval()
        for test_before, test_after in tqdm(test_data_loader, desc=description):
            test_before = test_before.to(device)
            test_after = test_after.to(device)

            logit = model(test_before, test_after)
            value = logit.squeeze(1).detach().cpu().float()

            test_value.extend(value)

    torch_label = torch.FloatTensor(test_value)
    np_label = torch_label.numpy()
    np_label[np.where(np_label<1)] = 1
    return np_label



def get_kfold_model_path(fold_path):
    fold_model_pathes = []
    each_fold = glob(os.path.join(fold_path, "*"))
    for fold in each_fold:
        if "fold" in fold:
            fold_model_pathes.extend(glob(os.path.join(fold, "*")))
    fold_model_pathes = [path for path in fold_model_pathes if path.endswith(".pt")]
    return fold_model_pathes



def main(args):

    TEST_PATH = "../data/test_dataset/"
    if args.inf_type.lower() == "fold":
        FOLD_PATH = os.path.join("./exp/", args.fold_path) if os.path.isdir(os.path.join("./exp/", args.fold_path)) else args.fold_path
        assert os.path.isdir(FOLD_PATH), "Wrong Model Path"
    elif args.inf_type.lower() == "single":
        SINGLE_PATH = args.single_path
        assert os.path.exists(SINGLE_PATH), "Wrong Model Path"
    device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
    assert args.submission_file.split(".")[-1] == "csv", "Wrong Output File Name"
    assert args.label_type.lower() in ["int", "float"], "Choose Label Type : int or float"

    # Make Inference Data
    test_set = pd.read_csv(os.path.join(TEST_PATH, 'test_data.csv'))
    submission = pd.read_csv(os.path.join(TEST_PATH, 'test_data.csv'))

    test_set['l_root'] = test_set['before_file_path'].map(lambda x: TEST_PATH + x.split('_')[1] + '/' + x.split('_')[2])
    test_set['r_root'] = test_set['after_file_path'].map(lambda x: TEST_PATH + x.split('_')[1] + '/' + x.split('_')[2])
    test_set['l_path'] = test_set['l_root'] + '/' + test_set['before_file_path'] + '.png'
    test_set['r_path'] = test_set['r_root'] + '/' + test_set['after_file_path'] + '.png'
    test_set['before_file_path'] = test_set['l_path']
    test_set['after_file_path'] = test_set['r_path']
    test_dataset = KistDataset(test_set, is_test=True)
    test_data_loader = DataLoader(test_dataset,
                                batch_size=64,
                                shuffle=False)

    if args.inf_type.lower() == "fold":
        # Get Fold Model Pathes
        model_list = get_kfold_model_path(FOLD_PATH)

        # Iteration : Model Load and Inference
        sum_labels = np.zeros(len(test_set))
        for idx, path in enumerate(model_list):
            # Load Model
            model = CompareNet(model_name=args.pretrained)
            checkpoint = torch.load(path)
            model.load_state_dict(checkpoint['model'])
            model = model.to(device)
            sum_labels = sum_labels + inference(model, test_data_loader, device, idx)
        mean_labels = sum_labels/len(model_list)
    
    elif args.inf_type.lower() == "single":
        model = CompareNet(model_name=args.pretrained)
        checkpoint = torch.load(SINGLE_PATH)
        model.load_state_dict(checkpoint['model'])
        model = model.to(device)
        mean_labels = inference(model, test_data_loader, device, "single")

    if args.label_type.lower() == "int":
        label = [round(n) for n in mean_labels]
    elif args.label_type.lower() == "float":
        label = mean_labels

    new_sub = pd.DataFrame({
        "idx" : submission['idx'],
        "time_delta" : label
    })
    new_sub.to_csv(args.submission_file, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="inference setter")
    parser.add_argument("--fold_path", type=str, default=None)
    parser.add_argument("--pretrained", type=str, default="regnetx_016")
    parser.add_argument("--submission_file", type=str, default="./submission.csv")
    parser.add_argument("--label_type", type=str, default="float")
    parser.add_argument("--inf_type", type=str, default="fold", help="fold or single")
    parser.add_argument("--single_path", type=str, default=None, help="used when single inference")
    args = parser.parse_args()
    print(args)
    main(args)