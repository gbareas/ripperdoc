"""Train the spectral-classification CNN. Runtime: about 10 h on one A100 (200 epochs).
Writes checkpoints/ and training_log.csv; the final evaluation is done by eval.py."""
import argparse, csv, torch
from model import SpectraCNN
from data import load_split

ap = argparse.ArgumentParser()
ap.add_argument("--epochs", type=int, default=200)
ap.add_argument("--seed", type=int, default=0)
args = ap.parse_args()
torch.manual_seed(args.seed)

train, val = load_split("train"), load_split("val")
net = SpectraCNN().cuda()
opt = torch.optim.AdamW(net.parameters(), lr=3e-4, weight_decay=0.05)
sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
with open("training_log.csv", "w", newline="") as f:
    log = csv.writer(f)
    log.writerow(["epoch", "train_loss", "val_loss", "val_acc"])
    for epoch in range(args.epochs):
        tl = net.fit_epoch(train, opt)
        vl, va = net.evaluate(val)
        sched.step()
        log.writerow([epoch, f"{tl:.4f}", f"{vl:.4f}", f"{va:.4f}"])
        torch.save(net.state_dict(), f"checkpoints/epoch{epoch:03d}.pt")
