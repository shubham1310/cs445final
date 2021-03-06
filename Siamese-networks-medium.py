import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import torchvision
import torchvision.datasets as dset
import torchvision.transforms as transforms
from torch.utils.data import DataLoader,Dataset
import torchvision.utils
import numpy as np
import random
from PIL import Image
import torch
from torch.autograd import Variable
import PIL.ImageOps    
import torch.nn as nn
from torch import optim
import torch.nn.functional as F
import os

from sklearn.metrics import confusion_matrix
import argparse

from models import SiameseNetwork2, DotProduct, Neuralloss, ContrastiveLoss #Deconv,
from tensorboard_logger import configure, log_value

from utils import PairDataset, SingleImage, SimplePairDataset, plot_confusion_matrix
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import classification_report, accuracy_score

parser = argparse.ArgumentParser()
parser.add_argument('--batchsize', type=int, default=16, help='input batch size')
parser.add_argument('--lr', type=float, default=0.0005, help='learning rate')
parser.add_argument('--nEpochs', type=int, default=50, help='number of epochs to train for')
parser.add_argument('--netG', type=str, default='', help="path to netG (to continue training)")
parser.add_argument('--out', type=str, default='checkpoints', help='folder to output model checkpoints')
parser.add_argument('--train', type=int, default=1, help='training 1/ testing 0')
parser.add_argument('--mainloss', type=int, default=0, help='Neural 1/ ContrastiveLoss 0/Dot 2')
parser.add_argument('--losstype', type=int, default=1, help='MSE 1/ BCE 0')
parser.add_argument('--dataset', type=str, default='cal101', help='oxford/all/other/cal101/cal256')
parser.add_argument('--pretrain', type=int, default=1, help='pretrain 1/0 ')
parser.add_argument('--datasettype', type=int, default=1, help='Same V/S different - 0/ Normal retrieval 1 ')
parser.add_argument('--numneigh', type=int, default=3, help='Number of neighbors for Classifier')
parser.add_argument('--cnfmat', type=int, default=0, help='Confusion matrix')

opt = parser.parse_args()
print(opt)

try:
    os.makedirs(opt.out)
except OSError:
    pass

if opt.dataset=='oxford':
    print('oxford dataset')
    training_dir = "./newdata/training/"
    testing_dir = "./newdata/testing/"
elif opt.dataset=='other':
    print('IIA30 dataset')
    training_dir = "./otherdata/training/"
    testing_dir = "./otherdata/testing/"
elif opt.dataset=='cal101':
    print('Caltech 101 dataset')
    training_dir = "./cal101/training/"
    testing_dir = "./cal101/testing/"
elif opt.dataset=='cal256':
    print('Caltech 256 dataset')
    training_dir = "./cal256/training/"
    testing_dir = "./cal256/testing/"
elif opt.dataset=='all':
    print('combined dataset')
    training_dir = "./datadiv/training/"
    testing_dir = "./datadiv/testing/"
else:
    print('dataset missing')

configure('logs/genimage-' + str(opt.out), flush_secs=5)

transform =transforms.Compose([transforms.Resize((224,224)),
                              transforms.ToTensor(),
                            transforms.Normalize(mean = [0.485, 0.456, 0.406],
                                                std = [0.229, 0.224, 0.225]),
                              ])


convnet = SiameseNetwork2(opt.pretrain).cuda()
if opt.netG != '':
    convnet.load_state_dict(torch.load(opt.netG))


if opt.train:
    if opt.mainloss==1:
        print("Neuralloss")
        criterion = Neuralloss(opt.losstype).cuda()
    elif opt.mainloss==0:
        print("Contrastive loss")
        criterion = ContrastiveLoss().cuda()
    else:
        print("Dot product loss")
        criterion = DotProduct(opt.losstype).cuda()


    if opt.datasettype==0:
        print("Same v/s different dataset")
        siamese_dataset = SimplePairDataset(imageFolder=training_dir,
                                    transform=transform)
    else:
        # print("Normal dataset")
        siamese_dataset = PairDataset(imageFolder=training_dir,
                                    transform=transform)

    train_dataloader = DataLoader(siamese_dataset,
                            shuffle=True,
                            num_workers=8,
                            batch_size=opt.batchsize)
    # optimizer = optim.Adam(list(convnet.parameters()) + list(criterion.parameters()),lr = 0.0005 )
    optimizer = optim.SGD(convnet.parameters(), lr=opt.lr, momentum=0.9, nesterov=True)
    iteration_number= 0

    
    for epoch in range(0,opt.nEpochs):
        epochloss=0
        iterloss=0
        for i, data in enumerate(train_dataloader,0):
            convnet.zero_grad()
            img0, img1 , label = data
            img0, img1 , label = Variable(img0).cuda(), Variable(img1).cuda() , Variable(label).cuda()
            output1,output2 = convnet(img0),convnet(img1)
            loss= criterion(output1,output2,label)
            loss.backward()
            optimizer.step()
            epochloss+=loss.data[0]
            iterloss+=loss.data[0]

            if i %30 == 0 :
                print("[%d/%d][%d/%d] Main Loss: %.4f"%(epoch, opt.nEpochs,i,len(train_dataloader) ,loss.data[0]))
                iteration_number +=1
                log_value('Netloss', iterloss/30, iteration_number)
                iterloss=0
            if iteration_number%10==0:
                torch.save(convnet.state_dict(), '%s/netconv%d.pth' % (opt.out, iteration_number/10))
        log_value('Epoch loss', epochloss/len(train_dataloader), epoch)
else:
    folderenum={}
    count=1
    folders = os.listdir(training_dir)
    target_names=['other']
    for folder in folders:
        if os.path.isdir(training_dir + folder) and not(folder[:5] == 'other'):
            folderenum[folder] = count
            count+=1
            target_names.append(folder)
        elif os.path.isdir(training_dir + folder):
            folderenum[folder] = 0
    # print(folderenum)
    print('Enumeration done')
    single_dataset = SingleImage(imageFolder=training_dir, enumdict = folderenum, transform=transform)

    train_dataloader = DataLoader(single_dataset,
                            shuffle=True,
                            num_workers=8,
                            batch_size=opt.batchsize)
    images=[]
    labels=[]
    for i, data in enumerate(train_dataloader,0):
        img0, label = data
        img0 = Variable(img0).cuda()
        output = convnet(img0)
        for j in range(len(label)):
            images.append(output[j].data.cpu().numpy())
            labels.append(label[j])
        if i%100==0:
            print('Data creation done for %d/%d'%(i,len(train_dataloader)))

    print('Image and labels done')
    # for k in range(3,10):
    print('Using %d number of neighbours'%(opt.numneigh) )
    neigh = KNeighborsClassifier(n_neighbors=opt.numneigh)
    neigh.fit(images, labels)

    print('Nearest neighbours Classifier trained')

    single_dataset = SingleImage(imageFolder=testing_dir, enumdict = folderenum, transform=transform)

    test_dataloader = DataLoader(single_dataset,
                shuffle=True,
                num_workers=8,
                batch_size=opt.batchsize)

    act=[]
    pred=[]
    for i, data in enumerate(test_dataloader,0):
        img0, label = data
        img0= Variable(img0).cuda()
        output = convnet(img0)
        for j in range(len(label)):
            act.append(label[j])
            x=neigh.predict([output[j].data.cpu().numpy()])
            pred.append(x[0])
            # print(label[j],x[0])
        if i%50==0:
            print('Prediction done for %d/%d'%(i,len(test_dataloader)))
    print(classification_report(act, pred, target_names=target_names))
    print(accuracy_score(act, pred))

    if opt.cnfmat:
        # Compute confusion matrix
        cnf_matrix = confusion_matrix(act, pred)
        np.set_printoptions(precision=2)

        # # Plot non-normalized confusion matrix
        # plt.figure()
        # plot_confusion_matrix(cnf_matrix, classes=target_names,
        #                       title='Confusion matrix, without normalization')
        # plt.savefig('cnf_unnorm.png')

        # Plot normalized confusion matrix
        plt.figure(figsize=(13, 13))
        plot_confusion_matrix(cnf_matrix, classes=target_names, normalize=True,
                              title='Normalized confusion matrix')

        # plt.show()
        plt.savefig('iia30cnf_normsmall.png')


