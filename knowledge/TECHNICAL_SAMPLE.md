# Machine Learning System for Image Classification

## Objective
The primary objective of this project is to develop a high-accuracy image classification system using deep learning. The goal is to achieve 95% accuracy on the benchmark dataset.

## Dataset
We used the CIFAR-10 dataset for training and evaluation. This dataset contains 60,000 images across 10 classes. The dataset is split into 50,000 training samples and 10,000 test samples.

## Algorithm
We implemented a Convolutional Neural Network (CNN) architecture using PyTorch. The model consists of 5 convolutional layers followed by 3 fully connected layers. We used the Adam optimizer with a learning rate of 0.001.

## Architecture
The system architecture follows a standard CNN pipeline: input layer, convolutional layers with ReLU activation, max pooling layers, dropout regularization, and softmax output. The framework is built using PyTorch and trained on an NVIDIA GPU.

## Results
Our CNN model achieved 94.2% accuracy on the CIFAR-10 test set. The precision was 93.8% and recall was 94.1%. The F1-score reached 93.9%. This represents a 2.1% improvement over the baseline ResNet model.

## Technology
The implementation uses Python 3.10, PyTorch 2.0, and CUDA 11.8. Data preprocessing used NumPy and Pandas. The training was performed on a single NVIDIA A100 GPU.

## Requirements
The system requires at least 16GB of GPU memory for training. The software requires Python 3.8 or higher and PyTorch 1.12 or higher.
