
# coding: utf-8

# In[103]:


from skimage import io
import sys
import torch
import torch.nn as nn
import pandas as pd
import os
from torch.utils.data import Dataset, DataLoader
import numpy as np
from torch.utils.data.dataset import Dataset
import torchvision
import torchvision.transforms as transforms
import torch.utils.data as data_utils
import time
import math
import pickle as pkl
import matplotlib.pyplot as plt
import random
from random import shuffle
from collections import namedtuple
from tqdm import tqdm_notebook


# In[104]:


start = time.time()


# In[105]:


sequence_length = 300
input_size = 378
hidden_size = 64
num_layers = 2
num_classes = 2 # Depressed or not depressed
batch_size = 50
num_epochs = 10
learning_rate = 0.001
rec_dropout = 0.05
feature_len = 378


# In[106]:


class RNN(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_classes):    
        super(RNN, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, dropout = rec_dropout, batch_first = True)
#         self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first = True)
        self.fc = nn.Linear(hidden_size, num_classes) 
    
    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)

        out, _ = self.lstm(x, (h0, c0))

        out = self.fc(out[:, -1, :])
        return out


# In[107]:


class faceFeatures(Dataset):
    def __init__(self, root_dir, csv_file, transform=None):
        self.features_frame = pd.read_csv(root_dir + csv_file)
        self.transform = transform
        self.csv_file = csv_file

    def __len__(self):
        return len(self.features_frame)
 
    def __getitem__(self):
        features = np.zeros((sequence_length, feature_len), dtype="float32")
        label = np.ones((1), dtype="int32")
        
        all_features = self.features_frame.iloc[:, 3:-1].values
        diff = sequence_length - all_features.shape[0]
        
        if (diff < 0):
            rows = all_features.shape[0]
            row_idx = 0
            print (rows)
            while(row_idx + sequence_length <= rows):
                if (row_idx == 0):
                    features = all_features[row_idx:row_idx+sequence_length,:]
                    print ("First matrix shape:" + str(features.shape))
                    label = self.features_frame.iloc[1, -1]
                else:
                    features = np.vstack((features, all_features[row_idx:row_idx+sequence_length,:]))
                    label = np.vstack((label, self.features_frame.iloc[1, -1]))
                    print ("Subsequent matrix shape:" + str(features.shape))

                row_idx = row_idx + sequence_length
                
                
            new_diff = sequence_length - (all_features.shape[0] - row_idx)
            print ("Difference is: " + str(new_diff) + str(self.csv_file))
            features_zeroes = np.zeros((new_diff, all_features.shape[1]))
            second_features = np.append(all_features[row_idx:all_features.shape[0],:], features_zeroes, axis = 0)
            features = np.vstack((features, second_features))
            print ("Final matrix shape:" + str(features.shape))

            label = np.vstack((label, self.features_frame.iloc[1,-1]))

            features = features.reshape((-1, sequence_length, feature_len))


        else:
            features_zeroes1 = np.zeros((int(diff/2), all_features.shape[1]))
            features_zeroes2 = np.zeros((int(diff/2)+1, all_features.shape[1]))
            temp_features = np.append(features_zeroes1, all_features, axis = 0)
            if (diff % 2 == 0):
                temp_features = np.append(temp_features, features_zeroes1, axis = 0)
            else:
                temp_features = np.append(temp_features, features_zeroes2, axis = 0)
            features = temp_features
            print ("Single feature" + str(features.shape))
            features = features.reshape(-1, sequence_length, input_size)
#             print (self.features_frame.iloc[1, -1])
            label = np.array([self.features_frame.iloc[1,-1]])   
#         print (features, label)
        print ("Final shape:" + str(features.shape))
        return (features, label)


# In[108]:


class concatFrames(Dataset):
    # Initialize the list of csv files
    def __init__(self, root_dir, _input, _label, csv_files = []):
        self.csv_files = csv_files
        self.root_dir = root_dir
        self._input = _input
        self._label = _label
        
    # Create tensor of frames
    def _concat_(self):
        data = faceFeatures(self.root_dir, self.csv_files[0])
        self._input, self._label = data.__getitem__()
        print ("loop outside")
        print (self._input.shape)
        # self._label = data.__getitem__()[1]
        
        for i in range(1, len(self.csv_files)):
            print (self.csv_files[i])
            data = faceFeatures(self.root_dir, self.csv_files[i])
            _feature_data, _label_data = data.__getitem__()
            for j in _feature_data:
                print ("loop")
                print (j.shape, self._input.shape)
                j = j.reshape(-1, sequence_length, input_size)
                self._input = self._input.reshape(-1, sequence_length, input_size)
                print (j.shape, self._input.shape)
                self._input = np.vstack((j, self._input))
            for j in _label_data:
                self._label = np.vstack((j, self._label))

        self._input = self._input.reshape((-1, sequence_length, feature_len))
        self._label = self._label.reshape((-1))
        print ("Concat :" + str(self._input.shape) + str(self._label.shape))
        return (self._input, self._label)

    # Get the tensor by index
    def __getitem__(self, idx):
        frame_name = self.csv_files[idx]
        frame_features = self._input[idx]
        frame_label = self._label[idx]
        return (frame_features, frame_label) 


# In[7]:


print ("Training data preprocessing....")
# csv_files = ["300_P_new/300_P1.csv", "302_P_new/302_P2.csv","300_P_new/300_P2.csv"]
csv_files_train = []
for filename in os.listdir("./frames_10fps/normalized"):
    if filename != "test" and filename != "validation": 
        for framefile in os.listdir("./frames_10fps/normalized/"+filename):
            file = filename + "/" + framefile
            csv_files_train.append(file)
# print (csv_files_train)
shuffle(csv_files_train)
print (len(csv_files_train))

_input = np.zeros((sequence_length, feature_len), dtype="float32")
_label = np.ones((1), dtype="int32")

# csv_files_ = ["303_P/303_P25.csv", "303_P/303_P16.csv" ,"303_P/303_P14.csv"]
data = concatFrames(root_dir = "./frames_10fps/normalized/", csv_files = csv_files_train, _input = _input, _label = _label)
_input, _label = data._concat_()

_input_train = torch.Tensor(np.array(_input))
_label_train = torch.Tensor(np.array(_label))
_label_train = (_label_train.type(torch.LongTensor))


torch.save(_input_train, "input_train_300_normalized.pt")
torch.save(_label_train, "label_train_300_normalized.pt")

# print (data.__getitem__(0))


# In[8]:


print ("Validation data preprocessing....")

csv_files_validation = []
for filename in os.listdir("./frames_10fps/normalized"):
    if filename == "validation": 
        for framefile in os.listdir("./frames_10fps/normalized/"+filename):
            file = filename + "/" + framefile
            csv_files_validation.append(file)
            
# print (len(csv_files_validation))
_input_ = np.zeros((sequence_length, feature_len), dtype="float32")
_label_ = np.ones((1), dtype="int32")
data_validation = concatFrames(root_dir = "./frames_10fps/normalized/", csv_files = csv_files_validation, _input = _input_, _label = _label_)
_input_validation, _label_validation = data_validation._concat_()
_input_validation = torch.Tensor(np.array(_input_validation))
_label_validation = torch.Tensor(np.array(_label_validation))
_label_validation = (_label_validation.type(torch.LongTensor))

torch.save(_input_validation, "input_validation_300_normalized.pt")
torch.save(_label_validation, "label_validation_300_normalized.pt")

print (_input_validation.shape)
print (data.__getitem__(0))


# In[9]:


print ("Test data preprocessing....")

csv_files_test = []
for filename in os.listdir("./frames_10fps/normalized"):
    if filename == "test": 
        for framefile in os.listdir("./frames_10fps/normalized/"+filename):
            file = filename + "/" + framefile
            csv_files_test.append(file)
            
# print (len(csv_files_test))
_input_ = np.zeros((sequence_length, feature_len), dtype="float32")
_label_ = np.ones((1), dtype="int32")
data_test = concatFrames(root_dir = "./frames_10fps/normalized/", csv_files = csv_files_test, _input = _input_, _label = _label_)
_input_test, _label_test = data_test._concat_()
_input_test = torch.Tensor(np.array(_input_test))
_label_test = torch.Tensor(np.array(_label_test))
_label_test = (_label_test.type(torch.LongTensor))

torch.save(_input_test, "input_test_300_normalized.pt")
torch.save(_label_test, "label_test_300_normalized.pt")

print (_input_test.shape)
# print (data.__getitem__(0))


# In[109]:


model = RNN(input_size, hidden_size, num_layers, num_classes)
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr = learning_rate)


# In[110]:


_input_train = torch.load("input_train_300_normalized.pt")
_label_train = torch.load("label_train_300_normalized.pt")
_input_validation = torch.load("input_validation_300_normalized.pt")
_label_validation = torch.load("label_validation_300_normalized.pt")


# In[111]:


# _input_train = torch.Tensor(_input_train)
# _label_train = torch.Tensor(_label_train)
# _input_validation = torch.Tensor(_input_validation)
# _label_validation = torch.Tensor(_label_validation)

# print (_input_train[0])


# In[112]:


_input_train = np.array(_input_train)
_label_train = np.array(_label_train)

# print (_input_validation.shape)

discard_size = _input_train.shape[0] % batch_size
# print (discard_size)


discard_idx = []
for i in range(0, discard_size):
    discard_idx.append(random.randint(0, _input_train.shape[0]))
    
discard_idx = sorted(discard_idx)
discard_idx = list(reversed(discard_idx))

# print (discard_idx)
for i in (discard_idx):
    _input_train = np.delete(_input_train, i, 0)
    _label_train = np.delete(_label_train, i, 0)
#     print (_input_train.shape)
#     print (_label_train.shape)
    

_input_train = torch.Tensor(_input_train)
_label_train = torch.Tensor(_label_train)
_label_train = (_label_train.type(torch.LongTensor))

train = data_utils.TensorDataset(_input_train, _label_train)
train_loader = data_utils.DataLoader(train, batch_size=batch_size, shuffle=True)
validation = data_utils.TensorDataset(_input_validation, _label_validation)
validation_loader = data_utils.DataLoader(validation, shuffle=True)
total_step = len(train_loader)

epoch_start = time.time()
loss = 0

batchTuple = namedtuple("batchTuple", "feature label batch_size")
for t in tqdm_notebook(range(20)):
    n_correct, n_total = 0, 0
    train_loss = []
    valid_loss = []
    train_acc_list = []
    valid_acc_list = []
    # i is the counter, ith batch, j is the value of batch
    # Training
    for i,(feature, label) in enumerate(train_loader):
        feature = feature.reshape(-1, sequence_length, input_size)
#         print (feature.shape)

        batch = batchTuple(feature = feature, label = label, batch_size = batch_size)
        
        # Forward pass
        outputs = model(feature)
#         print (outputs.shape)
#         print (label.shape)

        label = label.reshape(batch_size)

        # Calculate train accuracy
        _, predicted_t = torch.max(outputs.data, 1)
        n_correct += (torch.max(outputs, 1)[1].view(label.size()) == label).sum().item()
        n_total = n_total + label.size(0)
        train_acc = n_correct/n_total
        train_acc_list.append(train_acc)
        
        # Calculate loss
        loss = criterion(outputs, label)
        train_loss.append(loss.item())
        
        # Backward and optimize
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        
     # Validation
    with torch.no_grad():
        correct = 0
        total = 0

        for j, (images, labels) in enumerate(validation_loader):

            images = images.reshape(-1, sequence_length, input_size)
            outputs = model(images)
            _, predicted = torch.max(outputs.data, 1)
            total = total + labels.size(0)
            correct += (torch.max(outputs, 1)[1].view(labels.size()) == label).sum().item()
            d_loss = criterion(outputs, labels)
            valid_loss.append(d_loss)
                        
        valid_acc = correct/total
        valid_acc_list.append(valid_acc)
        
    print ("Training accuracy, Training loss, Validation loss, Validation Accuracy")  
    print (t, sum(train_acc_list)/len(train_acc_list), sum(train_loss)/len(train_loss), sum(valid_loss)/len(valid_loss), sum(valid_acc_list)/len(valid_acc_list))  
    

#     print ("Epoch time:")
#     print (time.time() - epoch_start)
#     epoch_start = time.time()

            
details = "hidden_size:" + str(hidden_size) + ",learning_rate:" + str(learning_rate) + ",dropout:" + str(rec_dropout)
print (details)

plt.figure() 
plt.plot(train_loss)
plt.title("Training loss " + str(details))
    
plt.figure()
plt.plot(train_acc_list)
plt.title("Training accuracy " + str(details))            

plt.figure()
plt.plot(valid_loss)
plt.title("Validation loss " + str(details))

plt.figure()
plt.plot(valid_acc_list)
plt.title("Validation accuracy " + str(details))



# In[ ]:


f_time = time.time()-start
print (f_time)

