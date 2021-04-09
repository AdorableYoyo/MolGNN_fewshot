import argparse

from loader import MoleculeDataset
from torch_geometric.data import DataLoader
from Chembl_loader import ChemBLFP 
import torch
import torch.nn as nn
import torch.nn.functional as F

import torch.optim as optim


from tqdm import tqdm
import numpy as np


from model import GNN, GNN_fingerprint
from sklearn.metrics import roc_auc_score, accuracy_score
from util import ONEHOT_ENCODING


def train( args, model, device, loader, optimizer, criterion):

    model.train()

    for step, batch in enumerate(tqdm(loader,desc='Iteration')):
        batch = batch.to(device)

        pred = model (batch.x, batch.edge_index, batch.edge_attr, batch.batch)

        y = batch.y
        y = y.float()
        pred = pred.float()
        assert (pred.size() == y.size())
        
        loss = criterion(pred, y) 

        # backprop
        optimizer.zero_grad()
        #loss.backward()
        #loss.sum().backward()
        loss.sum().backward()
        optimizer.step()


def eval (args, model,device, loader,criterion):

    model.eval()
    y_true = []
    y_scores = []
    for step, batch in enumerate(tqdm(loader, desc="Iteration")):
        batch = batch.to(device)

        with torch.no_grad():
            pred = model(batch.x, batch.edge_index, batch.edge_attr, batch.batch)
           # pred = model (batch.x, batch.edge_index,  batch.batch) 
        y_true.append(batch.y.cpu())
        y_scores.append(pred.cpu())
        y = batch.y
        y = y.float()
        pred = pred.float()
        loss = criterion(pred, y) 


    y_true = torch.cat(y_true, dim=0).cpu().numpy()
    y_scores = torch.cat(y_scores, dim=0).cpu().numpy()
    roc_list = []

    for i in range(y_true.shape[1]):
        # AUC is only defined when there is at least one positive and one negative data.
        if np.sum(y_true[:, i] == 1) > 0 and np.sum(y_true[:, i] == 0) > 0:

            roc_list.append(
                roc_auc_score(y_true[:, i], y_scores[:, i])
            )

  



    return roc_list

 
def main():
    # Training settings
    
    
    parser = argparse.ArgumentParser(description='PyTorch implementation of pre-training of fingerprint')

    parser.add_argument('--device', type=int, default=0,
                        help='which gpu to use if any (default: 0)')
    parser.add_argument('--batch_size', type=int, default=32,
                        help='input batch size for training (default: 32)')
    parser.add_argument('--epochs', type=int, default=100,
                        help='number of epochs to train (default: 100)')
    parser.add_argument('--lr', type=float, default=0.001,
                        help='learning rate (default: 0.001)')
    parser.add_argument('--decay', type=float, default=0,
                        help='weight decay (default: 0)')
    parser.add_argument('--num_layer', type=int, default=5,
                        help='number of GNN message passing layers (default: 5).')
    parser.add_argument('--emb_dim', type=int, default=256,
                        help='embedding dimensions (default: 300)')
    
    parser.add_argument(
        "--node_feat_dim", type=int, default=154, help="dimension of the node features.",
    )
    parser.add_argument(
        "--edge_feat_dim", type=int, default=2, help="dimension ofo the edge features."
    )


    parser.add_argument('--fingerprint_dim', type=int, default=740,
                        help='embedding dimensions of FP(default:740)')
    parser.add_argument('--graph_pooling', type=str, default="mean",
                    help='graph level pooling (sum, mean, max, set2set, attention)')
    parser.add_argument('--dropout_ratio', type=float, default=0.2,
                        help='dropout ratio (default: 0.2)')
    parser.add_argument('--JK', type=str, default="last",
                        help='how the node features across layers are combined. last, sum, max or concat')
    
    parser.add_argument('--dataset', type=str, default = 'chembl', help='root directory of dataset. For now, only fiingerprint.')
    parser.add_argument('--gnn_type', type=str, default="gine")
    parser.add_argument('--input_model_file', type=str, default = 'chemblFiltered_pretrained_model_with_contextPred', help='filename to read the model (if there is any)')
    parser.add_argument('--output_model_file', type = str, default = 'trained_model/pre_FP_chembl', help='filename to output the pre-trained model')
    parser.add_argument('--num_workers', type=int, default = 4, help='number of workers for dataset loading')
    args = parser.parse_args()
    
    print("show all arguments configuration...")
    print(args)


    torch.manual_seed(0)
    np.random.seed(0)
    device = torch.device("cuda:" + str(args.device)) if torch.cuda.is_available() else torch.device("cpu")
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(0)
    
    dataset_og = ChemBLFP(root=args.dataset)
    dataset = ChemBLFP(root=args.dataset , transform = ONEHOT_ENCODING(dataset = dataset_og))

    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True, num_workers = args.num_workers)
    #model = GNN_fingerprint(5, 300,fingerprint_dim=740, JK = 'last',  graph_pooling = "mean"  , drop_ratio = 0.2,  gnn_type = 'gin') 
    model =  GNN_fingerprint (args.num_layer, args.node_feat_dim, args.edge_feat_dim,args.emb_dim, args.fingerprint_dim, args.JK, args.graph_pooling, args.dropout_ratio, args.gnn_type)

    if not args.input_model_file == "":
            model.from_pretrained(args.input_model_file + ".pth")


    model.to(device)
#    print(f'model architecture:{model}')
    optimizer = optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.decay)  


    for epoch in range(1,args.epochs+1):
        print("====epoch " + str(epoch))

        train(args, model, device, loader, optimizer,criterion=nn.BCEWithLogitsLoss(reduction = "none"))

    if not args.output_model_file == "":
        torch.save(model.gnn.state_dict(), args.output_model_file + ".pth")  

if __name__ == "__main__":
    main()



