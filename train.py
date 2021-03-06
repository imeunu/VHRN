import argparse
import os

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

from data.dataloader import TrainSet
from loss import *
from networks.VHRN import *
from utils import utils


def train(args):
    torch.cuda.empty_cache()
    os.makedirs(args.ckpt, exist_ok=True)
    os.makedirs(args.log_dir, exist_ok=True)
    writer = SummaryWriter(args.log_dir)
    model = VHRN()
    model = nn.DataParallel(model).cuda()
    print('Loaded Model')
    criterion = laplace_loss
    optimizer = optim.AdamW(model.parameters(), lr = args.lr)
    scheduler = optim.lr_scheduler.MultiStepLR(optimizer,
                                milestones=args.milestones, gamma=args.gamma)
    clip_grad_D, clip_grad_T = args.clip_grad_D, args.clip_grad_T
    if args.resume:
        ckpt = f'{args.ckpt}/{str(args.resume).zfill(3)}.pth'
        ckpt = torch.load(ckpt)
        model.load_state_dict(ckpt['model_state_dict'])
        optimizer.load_state_dict(ckpt['optimizer_state_dict'])
        scheduler.load_state_dict(ckpt['lr_scheduler_state_dict'])
        start_epoch = args.resume
    else:
        model = utils.he_init(model)
        start_epoch = 0
    trainset = TrainSet(args)
    trainset = DataLoader(trainset, shuffle=True, batch_size=args.batch_size,
                            num_workers=8, pin_memory=True)
    print('Loaded Data')

    param_D = [x for name, x in model.named_parameters() if 'dnet' in name.lower()]
    param_T = [x for name, x in model.named_parameters() if 'tnet' in name.lower()]

    model.train()
    length = len(trainset)
    for epoch in range(start_epoch, args.epoch):
        running_loss = lh_loss = trans_loss = dehaze_loss = 0
        grad_norm_D = grad_norm_T = 0
        with tqdm(total=length, desc=f'Epoch {epoch+1}', ncols=70) as pbar:
            for i, batch in enumerate(trainset):
                clear, hazy, trans, A = [x.cuda().float() for x in batch]
                optimizer.zero_grad()
                dehaze_est, trans_est = model(hazy, 'train')
                loss, lh, kl_dehaze, kl_trans = criterion(hazy, dehaze_est, trans_est, clear, trans, A, sigma=1e-6, eps1=args.eps, eps2=args.eps)
                loss.backward()

                total_norm_D = nn.utils.clip_grad_norm_(param_D, clip_grad_D)
                total_norm_T = nn.utils.clip_grad_norm_(param_T, clip_grad_T)
                grad_norm_D = (grad_norm_D*(i/(i+1)) + total_norm_D/(i+1))
                grad_norm_T = (grad_norm_T*(i/(i+1)) + total_norm_T/(i+1))

                optimizer.step()
                running_loss += loss.item()/length
                lh_loss += lh.item()/length
                trans_loss += kl_trans.item()/length
                dehaze_loss += kl_dehaze.item()/length
                pbar.update(1)
        scheduler.step()
        writer.add_scalar('Loss', running_loss, epoch)
        writer.add_scalar('Likelihood', lh, epoch)
        writer.add_scalar('Transmission', trans_loss, epoch)
        writer.add_scalar('Dehazer', dehaze_loss, epoch)
        torch.save({'model_state_dict': model.state_dict(),
                    'optimizer_state_dict': optimizer.state_dict(),
                    'lr_scheduler_state_dict': scheduler.state_dict()
                    }, f'{args.ckpt}/{str(epoch+1).zfill(3)}.pth')

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch_size', type=int, default=16)
    parser.add_argument('--lr', type=float, default=2e-4)
    parser.add_argument('--train_path', type=str, default='/home/eunu/nas/reside/in_train.h5')
    parser.add_argument('--ckpt', type=str, default='/home/eunu/nas/vhrn_ckpt/1e-7')
    parser.add_argument('--epoch', type=int, default=200)
    parser.add_argument('--milestones', type=list, default=[20,40,70,100,150])
    parser.add_argument('--gamma', type=float, default=0.5)
    parser.add_argument('--clip_grad_D', type=float, default=1e4)
    parser.add_argument('--clip_grad_T', type=float, default=1e3)
    parser.add_argument('--log_dir', type=str, default='./log/1e-7')
    parser.add_argument('--patch_size', type=int, default=256)
    parser.add_argument('--augmentation', type=bool, default=True)
    parser.add_argument('--eps', type=float, default=1e-7)

    parser.add_argument('--cuda', type=int, default=1)
    parser.add_argument('--resume', type=int, default=0)
    return parser.parse_args()

if __name__ == '__main__':
    args = get_args()
    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    if isinstance(args.cuda, int):
        os.environ['CUDA_VISIBLE_DEVICES'] = str(args.cuda)
    else:
        os.environ['CUDA_VISIBLE_DEVICES'] = ','.join(str(x) for x in list(args.cuda))
    train(args)