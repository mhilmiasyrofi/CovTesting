from util import get_data, get_model
from tensorflow.python.client import device_lib
from keras.preprocessing.image import ImageDataGenerator
from art.data_generators import KerasDataGenerator

from art.classifiers import KerasClassifier
from art.attacks import ProjectedGradientDescent
from art.attacks import BasicIterativeMethod
from art.defences import AdversarialTrainer
from art.attacks import CarliniL2Method
from art.attacks import FastGradientMethod

import numpy as np
import tensorflow as tf
import os


DATA_DIR = "../data/"
MODEL_DIR = "../models/"

####for solving some specific problems, don't care
config = tf.ConfigProto()
config.gpu_options.allow_growth = True
sess = tf.Session(config=config)

# the data is in range(-.5, .5)
def load_data(dataset_name):
    assert (dataset_name.upper() in ['MNIST', 'CIFAR', 'SVHN'])
    dataset_name = dataset_name.lower()
    x_train = np.load(DATA_DIR + dataset_name + '/benign/x_train.npy')
    y_train = np.load(DATA_DIR + dataset_name + '/benign/y_train.npy')
    x_test = np.load(DATA_DIR + dataset_name + '/benign/x_test.npy')
    y_test = np.load(DATA_DIR + dataset_name + '/benign/y_test.npy')
    return x_train, y_train, x_test, y_test


def check_data_path(dataset_name):
    assert os.path.exists(DATA_DIR + dataset_name + '/benign/x_train.npy')
    assert os.path.exists(DATA_DIR + dataset_name + '/benign/y_train.npy')
    assert os.path.exists(DATA_DIR + dataset_name + '/benign/x_test.npy')
    assert os.path.exists(DATA_DIR + dataset_name + '/benign/y_test.npy')


def call_function_by_attack_name(attack_name):

    return {
        'FGSM': FastGradientMethod, # eps=0.2, batch_size=512
        'PGD': ProjectedGradientDescent # eps=8/255, eps_step=1/255, max_iter=20, batch_size=512)
    }[attack_name]

if __name__ == "__main__":
    datasets = ['mnist', 'svhn', 'cifar']
    model_dict = {
                'mnist': ['lenet1', 'lenet4', 'lenet5'],
                'cifar': ['vgg16', 'resnet20'],
                'svhn' : ['svhn_model', 'svhn_second', 'svhn_first']
                }

    # Check path
    for dataset_name in model_dict.keys():
        # verify data path
        check_data_path(dataset_name)
        # verify model path
        for model_name in model_dict[dataset_name]:
            model_path = "{}{}/{}.h5".format(MODEL_DIR, dataset_name, model_name)
            assert os.path.exists(model_path)

    attack_names = ['PGD']
    for attack_name in attack_names:
        for dataset in datasets:
            for model_name in model_dict[dataset]:
                x_train, y_train, x_test, y_test = load_data(dataset)

                from keras.models import load_model
                model_path = "{}{}/{}.h5".format(MODEL_DIR, dataset, model_name)
                model = load_model(model_path)
                model.compile(
                    loss='categorical_crossentropy',
                    optimizer='adam',
                    metrics=['accuracy']
                )

                model.summary()

                # Evaluate the benign trained model on clean test set
                labels_true = np.argmax(y_test, axis=1)
                labels_test = np.argmax(model.predict(x_test), axis=1)
                print('Accuracy test set: %.2f%%' % (np.sum(labels_test == labels_true) / x_test.shape[0] * 100))

                classifier = KerasClassifier(clip_values=(-0.5, 0.5), model=model, use_logits=False)
                attack = call_function_by_attack_name(attack_name)(classifier, eps=8/255, eps_step=1/255, max_iter=20, batch_size=512)

                x_test_pgd = attack.generate(x_test, y_test)

                # Evaluate the benign trained model on adv test set
                labels_pgd = np.argmax(classifier.predict(x_test_pgd), axis=1)
                print('Accuracy on original ' + attack_name + ' adversarial samples: %.2f%%' %
                    (np.sum(labels_pgd == labels_true) / x_test.shape[0] * 100))

                # Adversarial Training
                trainer = AdversarialTrainer(classifier, attack, ratio=1.0)
                trainer.fit(x_train, y_train, nb_epochs=160, batch_size=1024)

                # Save model
                classifier.save(filename= 'adv_' + model_name + '_' + attack_name + '.h5', path="{}{}".format(MODEL_DIR, dataset_name))

                # Evaluate the adversarially trained model on clean test set
                labels_true = np.argmax(y_test, axis=1)
                labels_test = np.argmax(classifier.predict(x_test), axis=1)
                print('Accuracy test set: %.2f%%' % (np.sum(labels_test == labels_true) / x_test.shape[0] * 100))

                # Evaluate the adversarially trained model on original adversarial samples
                labels_pgd = np.argmax(classifier.predict(x_test_pgd), axis=1)
                print('Accuracy on original ' + attack_name + ' adversarial samples: %.2f%%' %
                    (np.sum(labels_pgd == labels_true) / x_test.shape[0] * 100))

                # Evaluate the adversarially trained model on fresh adversarial samples produced on the adversarially trained model
                x_test_pgd = attack.generate(x_test, y_test)
                labels_pgd = np.argmax(classifier.predict(x_test_pgd), axis=1)
                print('Accuracy on new ' + attack_name + ' adversarial samples: %.2f%%' % (np.sum(labels_pgd == labels_true) / x_test.shape[0] * 100))





