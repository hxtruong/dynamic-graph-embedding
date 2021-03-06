import os
from copy import deepcopy
from os import listdir
from os.path import join, exists, isfile
from time import time

import networkx as nx

from src.static_ge import TStaticGE
from src.utils.autoencoder import TAutoencoder
from src.utils.checkpoint_config import CheckpointConfig
from src.utils.model_utils import get_hidden_layer, handle_expand_model, save_custom_model, load_custom_model


class TDynGE(object):
    def __init__(self, graphs, embedding_dim, l1=0.001, l2=0.0005, alpha=0.2, beta=10, activation='relu'):
        super(TDynGE, self).__init__()
        if not graphs:
            raise ValueError("Must be provide graphs data")

        self.graphs = graphs
        self.size = len(graphs)
        self.embedding_dim = embedding_dim
        self.l1 = l1
        self.l2 = l2
        self.alpha = alpha
        self.beta = beta
        self.static_ges = []
        self.activation = activation

    def get_all_embeddings(self):
        return [ge.get_embedding() for ge in self.static_ges]

    def get_embedding(self, index):
        if index < 0 or index >= self.size:
            raise ValueError("index is invalid!")
        return self.static_ges[index].get_embedding()

    def get_all_reconstructions(self):
        ge: TStaticGE
        return [ge.get_reconstruction() for ge in self.static_ges]

    def _train_model(self, dy_ge_idx, filepath, batch_size, epochs,
                     skip_print, learning_rate, early_stop,
                     plot_loss=True, ck_config: CheckpointConfig = None, shuffle=False):
        ge: TStaticGE = self.static_ges[dy_ge_idx]

        start_time = time()
        ge.train(batch_size=batch_size, epochs=epochs, skip_print=skip_print, learning_rate=learning_rate,
                 ck_config=ck_config, early_stop=early_stop, plot_loss=plot_loss, shuffle=shuffle)
        training_time = time() - start_time

        save_custom_model(model=ge.get_model(), filepath=filepath)

        # Make sure saving the updated static_ge
        self.static_ges[dy_ge_idx] = ge
        return round(training_time, 2)

    def _create_static_ge(self, index, folder_path, prop_size, net2net_applied):
        '''
            Static_ge is always create new weight for index = 0 and expand model for other index >0
        :param index:
        :param folder_path:
        :param prop_size:
        :param net2net_applied:
        :return:
        '''
        if index >= len(self.graphs):
            raise ValueError("index is out of range graphs")

        g: nx.Graph = self.graphs[index]
        autoencoder: TAutoencoder = None
        input_dim = g.number_of_nodes()

        if index == 0:
            hidden_dims = get_hidden_layer(
                prop_size=prop_size,
                input_dim=input_dim,
                embedding_dim=self.embedding_dim
            )

            autoencoder = TAutoencoder(
                input_dim=input_dim,
                embedding_dim=self.embedding_dim,
                hidden_dims=hidden_dims,
                l1=self.l1,
                l2=self.l2,
                activation=self.activation
            )
        else:
            prev_ae = load_custom_model(filepath=join(folder_path, f"graph_{index - 1}"))
            autoencoder = handle_expand_model(model=prev_ae, input_dim=input_dim,
                                              prop_size=prop_size, net2net_applied=net2net_applied)

        ge = TStaticGE(G=g, model=autoencoder, alpha=self.alpha, beta=self.beta)
        return ge

    def train(self, folder_path, prop_size=0.3, batch_size=64, epochs=100, skip_print=5,
              net2net_applied=False, learning_rate=1e-6, ck_config: CheckpointConfig = None,
              early_stop=50, plot_loss=True, shuffle=False):
        '''

        :param folder_path:
        :param prop_size:
        :param batch_size:
        :param epochs:
        :param skip_print:
        :param net2net_applied:
        :param learning_rate:
        :param ck_config:
        :param early_stop:
        :param plot_loss:
        :param shuffle:
        :return:
        '''
        # Create folder for saving model if not existed
        if not exists(folder_path):
            os.makedirs(folder_path)

        training_time_sum = 0
        for i in range(len(self.graphs)):
            training_time = self.train_at(model_index=i, folder_path=folder_path, prop_size=prop_size,
                                          batch_size=batch_size, epochs=epochs, skip_print=skip_print,
                                          net2net_applied=net2net_applied, learning_rate=learning_rate,
                                          ck_config=ck_config, early_stop=early_stop, plot_loss=plot_loss,
                                          is_load_from_previous_model=True, shuffle=shuffle, call_in_class=True
                                          )
            training_time_sum += training_time
            # print(f"Training time in {training_time}s")
        return training_time_sum

    def train_at(self, model_index, folder_path, prop_size=0.4, batch_size=64, epochs=100, skip_print=5,
                 net2net_applied=False, learning_rate=0.001, ck_config: CheckpointConfig = None,
                 early_stop=50, plot_loss=True, is_load_from_previous_model=False, shuffle=False, call_in_class=False):
        '''
        To training a specific model.
        :param call_in_class:
        :param shuffle:
        :param model_index:
        :param folder_path:
        :param prop_size:
        :param batch_size:
        :param epochs:
        :param skip_print:
        :param net2net_applied:
        :param learning_rate:
        :param ck_config:
        :param early_stop:
        :param plot_loss:
        :param is_load_from_previous_model: for training new weight from previous model.
                If NOT, model will continue (resume) training
        :return:
        '''
        if not exists(folder_path):
            raise ValueError(f"{folder_path} is invalid path.")
        if not call_in_class:
            if len(self.static_ges) == 0:
                self.load_models(folder_path=folder_path)
            if model_index >= len(self.static_ges):
                raise ValueError(f"{model_index} is out of range")

        if is_load_from_previous_model:  # for begin training -> create new model to train
            ge = self._create_static_ge(index=model_index, folder_path=folder_path,
                                        prop_size=prop_size,
                                        net2net_applied=net2net_applied)
            if call_in_class and len(self.static_ges) == model_index:
                self.static_ges.append(ge)
            else:
                self.static_ges[model_index] = ge

        # Else for resume training
        updated_ck_config = deepcopy(ck_config)
        if updated_ck_config is not None:
            updated_ck_config.set_index(index=model_index)

        print(f"\t--- Graph {model_index} ---")
        training_time = self._train_model(dy_ge_idx=model_index, filepath=join(folder_path, f"graph_{model_index}"),
                                          batch_size=batch_size, epochs=epochs, learning_rate=learning_rate,
                                          skip_print=skip_print, early_stop=early_stop, plot_loss=plot_loss,
                                          ck_config=updated_ck_config, shuffle=shuffle)
        # print(f"Time in {training_time}s")
        return training_time

    def load_models(self, folder_path):
        print("Loading models...", end=" ")
        start_time = time()
        self.static_ges = []

        # Trick for get length of saved models
        files = [f for f in listdir(folder_path) if isfile(join(folder_path, f))]
        length = len(files) // 2

        if length != len(self.graphs):
            raise Exception("There are NO saved training data")

        for i in range(length):
            filepath = join(folder_path, f"graph_{i}")
            model = load_custom_model(filepath=filepath)

            ge = TStaticGE(G=self.graphs[i], model=model, alpha=self.alpha, beta=self.beta)
            self.static_ges.append(ge)
        print(f"{round(time() - start_time, 2)}s")

    def save_embeddings(self, folder_path):
        print("Saving embeddings...")
        if not exists(folder_path):
            os.makedirs(folder_path)
        for idx, ge in enumerate(self.static_ges):
            ge: TStaticGE
            ge.save_embedding(filepath=join(folder_path, f"_{idx}"))

    def load_embeddings(self, folder_path):
        if not exists(folder_path):
            raise ValueError("Folder is invalid.")

        embeddings = []
        for idx, ge in enumerate(self.static_ges):
            ge: TStaticGE
            embedding = ge.load_embedding(filepath=join(folder_path, f"_{idx}"))
            embeddings.append(embedding)
        return embeddings


if __name__ == "__main__":
    g1 = nx.gnm_random_graph(n=5, m=5, seed=6)
    g2 = nx.gnm_random_graph(n=12, m=20, seed=6)
    g3 = nx.gnm_random_graph(n=30, m=80, seed=6)
    g4 = nx.gnm_random_graph(n=300, m=800, seed=6)
    graphs = [g1, g2, g3, g4]

    ck_config = CheckpointConfig(number_saved=10, folder_path="../models/generate_ck")

    # graphs, _ = read_dynamic_graph(folder_path="../data/cit_hepth", convert_to_idx=True, limit=1)

    dy_ge = TDynGE(graphs=graphs, embedding_dim=2)
    # dy_ge.load_models(folder_path="../models/generate")
    dy_ge.train(prop_size=0.3, epochs=50, skip_print=50, net2net_applied=True, learning_rate=0.003,
                folder_path="../models/generate/", ck_config=ck_config,
                early_stop=50, plot_loss=True)

    # dy_ge.train_at(model_index=1, prop_size=0.4, epochs=100, skip_print=20, net2net_applied=False, learning_rate=0.003,
    #                folder_path="../models/generate/", ck_config=ck_config,
    #                early_stop=50, plot_loss=True, is_load_from_previous_model=True)

    # dy_ge.train(prop_size=0.4, epochs=100, skip_print=5, net2net_applied=False, learning_rate=0.003,
    #             folder_path="../models/generate/", from_loaded_model=False, checkpoint_config=checkpoint_config, early_stop=50)

    print("Show embedding:")
    embeddings_list = dy_ge.get_all_embeddings()
    # for e in embeddings_list:
    #     plot_embedding(embeddings=e)

# 9.43 ; 18.93 ; 41.82
