import numpy as np
import cv2
import glob
import os,errno
from sklearn.cluster import KMeans
from shutil import copyfile
import pickle
import math
from pathlib import Path

data_path = '/home/lavisha/Downloads/101categories'
data_dir = ''.join([data_path, '/*.jpg'])
list1 = os.listdir(data_path) 
data = sorted(glob.glob(data_dir))
n = len(data)
ind = np.arange(n)
ind = np.random.permutation(ind)
trainno = int(0.8*n)
print("Training on ", trainno, "images")
print("Testing on ", n-trainno, "images")
trainind = ind[:trainno]
testind = ind[trainno:]
datatrain = list( data[i] for i in trainind )
datatest = list( data[i] for i in testind )
np.save('datatest',datatest)
np.save('datatrain',datatrain)
no_images = len(datatrain)
count_leaf = 0
no_feature = 0
feature_dim = 128
max_feature = 300
no_clusters = 6
no_levels = 8



tfidf = []
q1 = '/home/lavisha/Downloads/cs445_Project/im_key.npy'
q1 = Path(q1)
if q1.is_file():
	os.remove('/home/lavisha/Downloads/cs445_Project/im_key.npy')

q1 = '/home/lavisha/Downloads/cs445_Project/keypoints.npy'
q1 = Path(q1)
if q1.is_file():
	os.remove('/home/lavisha/Downloads/cs445_Project/keypoints.npy')

q1 = '/home/lavisha/Downloads/cs445_Project/tfidf.npy'
q1 = Path(q1)
if q1.is_file():
	os.remove('/home/lavisha/Downloads/cs445_Project/tfidf.npy')

q1 = '/home/lavisha/Downloads/cs445_Project/imgdic.npy'
q1 = Path(q1)
if q1.is_file():
	os.remove('/home/lavisha/Downloads/cs445_Project/imgdic.npy')

q1 = '/home/lavisha/Downloads/cs445_Project/ktree.pkl'
q1 = Path(q1)
if q1.is_file():
	os.remove('/home/lavisha/Downloads/cs445_Project/ktree.pkl')
		

class node:
	def __init__(self):
		self.val = None
		self.leaf = -1
		self.children = []

#Hierarchial clustering of the keypoints
def clustering(X, level, n2):
	#print("Reached",n2)
	global count_leaf
	#print("level:",level)	
	if(level>no_levels or len(X)<no_clusters):
		n2.leaf = count_leaf
		print("leaf:",count_leaf)
		count_leaf+=1
		return 
	kmeans = KMeans(n_clusters=no_clusters).fit(X)
	labels = kmeans.labels_
	clusters = [[] for i in range(no_clusters)]
	n2.val = kmeans
	for i in range(len(X)):
		#print("i:",i,"sizeofX",len(X),"labelsize",len(labels))
		clusters[labels[i]].append(X[i]);
	for i in range(no_clusters):
		temp = node()
		#print("just created",temp)
		n2.children.append(temp)
		clustering(clusters[i], level+1, n2.children[i])
	
	return n2

# Determining the clusterno of a keypoint
def findcluster(pt,n2):	
	i = n2.val.predict(pt)[0]
	#print("into cl:",i)
	if(n2.children[i].leaf!=-1):
		 return n2.children[i].leaf
	else:
		return findcluster(pt,n2.children[i])
	

print("1.Extracting SIFT keypoints from all images")
sift = cv2.xfeatures2d.SIFT_create()
numlimit = min(600,no_images )
keypoints = np.zeros((numlimit*max_feature,feature_dim))
ct = 0
im_key = [i for i in range(no_images)]
for filename in datatrain:
	print(filename)
	img = cv2.imread(filename)
	gray= cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
	kp, des = sift.detectAndCompute(gray,None)
	no_key = min(max_feature,len(des))
	im_key[ct] = no_key
	ct+=1	
	keypoints[no_feature:no_feature + no_key,:] = des[0:no_key,:]
	if ct==numlimit:
		break
	no_feature+=no_key

np.save('keypoints',keypoints)
np.save('im_key',im_key)
print("Keypoint extraction done!")
#duration = 1  # second
#freq = 440  # Hz
#os.system('play --no-show-progress --null --channels 1 synth %s sine %f' % (duration, freq))
print("2.Building K-tree")
n1 = node()
n1 = clustering(keypoints[0:no_feature], 1, n1)	

ktree_filename = 'ktree.pkl'
ktree_pkl = open(ktree_filename, 'wb')
pickle.dump(n1, ktree_pkl)
ktree_pkl.close()

print("3.Populating ktree via tf-idf (for all images in dataset)")
tfidf = [{} for i in range(count_leaf)]
imgdic = [{} for i in range(no_images)]
"""
ctr = 0
for j in range(no_images):
	print("image:",j)
	m = im_key[j]
	for i in range(m):
		pt = keypoints[ctr+i]
		pt1 = np.reshape(pt,(1,len(pt)))
		leafval = findcluster(pt1,n1)
		#print("keypoint:", ctr+i,":",pt1, "leaf:",leafval)
		if j in tfidf[leafval]:
			tfidf[leafval][j]+=1
		else:
			tfidf[leafval][j] = 1
		if leafval in imgdic[j]:
			imgdic[j][leafval]+=1
		else:
			imgdic[j][leafval] = 1 	
	ctr+=m
"""
j=0
for filename in datatrain:
	print("image:",j)
	img = cv2.imread(filename)
	gray= cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
	kp, des = sift.detectAndCompute(gray,None)
	no_key = min(300,len(des))		
	m = no_key
	for i in range(m):
		pt = des[i]
		pt1 = np.reshape(pt,(1,len(pt)))
		leafval = findcluster(pt1,n1)
		if j in tfidf[leafval]:
			tfidf[leafval][j]+=1
		else:
			tfidf[leafval][j] = 1
		if leafval in imgdic[j]:
			imgdic[j][leafval]+=1
		else:
			imgdic[j][leafval] = 1 	
	j+=1

for j in range(no_images):
	sum1 = 0
	for key in imgdic[j]:
		len1 = len(tfidf[key])
		imgdic[j][key] = imgdic[j][key]*(math.log(float(no_images)/len1)+1)
		sum1+=(imgdic[j][key]**2)
	sum1 = np.sqrt(sum1)	
	for key in imgdic[j]:
		imgdic[j][key]/=sum1

print("All tfidf scores set")
np.save('tfidf',tfidf)
np.save('imgdic',imgdic)
max1 = 0
min1 = 10000000000
for dd in tfidf:
	max1 = max(max1,len(dd))
	min1 = min(min1,len(dd))

print("Max length of tfidf:", max1, "Min length of tfidf:", min1)
#duration = 1  # second
#freq = 440  # Hz
#os.system('play --no-show-progress --null --channels 1 synth %s sine %f' % (duration, freq))
