from copy import deepcopy
from os import listdir
from os.path import join, exists, isfile
import os
from time import time
import networkx as nx
import torch
from torch.autograd import Variable

from src.data_preprocessing.graph_preprocessing import read_dynamic_graph
from src.static_ge import TStaticGE
from src.utils.autoencoder import TAutoencoder
from src.utils.checkpoint_config import CheckpointConfig
from src.utils.model_utils import get_hidden_layer, handle_expand_model, save_custom_model, load_custom_model
from src.utils.visualize import plot_embedding


class TDynGE(object):
    def __init__(self, graphs, embedding_dim, l1=0.001, l2=0.001, alpha=0.01, beta=2):
        super(TDynGE, self).__init__()
        if not graphs:
            raise ValueError("Must be provide graphs data")

        self.graphs = graphs
        self.graph_len = len(graphs)
        self.embedding_dim = embedding_dim
        self.l1 = l1
        self.l2 = l2
        self.alpha = alpha
        self.beta = beta
        self.static_ges = []
        self.model_folder_paths = []

    def get_all_embeddings(self):
        return [ge.get_embedding() for ge in self.static_ges]

    def get_embedding(self, index):
        if index < 0 or index >= self.graph_len:
            raise ValueError("index is invalid!")
        return self.static_ges[index].get_embedding()

    def _train_model(self, dy_ge_idx, filepath, batch_size, epochs,
                     skip_print, learning_rate, early_stop,
                     plot_loss=False, ck_config: CheckpointConfig = None):
        ge: TStaticGE = self.static_ges[dy_ge_idx]

        start_time = time()
        ge.train(batch_size=batch_size, epochs=epochs, skip_print=skip_print, learning_rate=learning_rate,
                 ck_config=ck_config, early_stop=early_stop, plot_loss=plot_loss)
        training_time = time() - start_time

        save_custom_model(model=ge.get_model(), filepath=filepath)

        # Make sure saving the updated static_ge
        self.static_ges[dy_ge_idx] = ge
        return round(training_time, 2)

    def _get_static_ge(self, index, folder_path, prop_size, net2net_applied, is_load_from_disk=False,
                       is_load_from_previous=False):
        if index >= len(self.graphs):
            raise ValueError("index is out of range graphs")

        g: nx.Graph = self.graphs[index]
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
            )
        else:
            # TODO: should have optional for using current model immediately
            prev_ae = load_custom_model(filepath=join(folder_path, f"graph_{index - 1}"))
            # prev_ae = self.static_ges[index - 1].get_model()
            autoencoder = handle_expand_model(model=prev_ae, input_dim=input_dim,
                                              prop_size=prop_size, net2net_applied=net2net_applied)

        ge = TStaticGE(G=g, model=autoencoder, alpha=self.alpha, beta=self.beta)
        return ge

    def train(self, folder_path, prop_size=0.4, batch_size=64, epochs=100, skip_print=5,
              net2net_applied=False, learning_rate=0.001, ck_config: CheckpointConfig = None,
              from_loaded_model=False, early_stop=50, model_index=None, plot_loss=False):
        if not exists(folder_path):
            raise ValueError(f"{folder_path} is invalid path.")

        if not from_loaded_model:
            # Create folder for saving model if not existed
            if not exists(folder_path):
                os.makedirs(folder_path)

            for i in range(len(self.graphs)):
                ge = self._get_static_ge(index=i, folder_path=folder_path, prop_size=prop_size,
                                         net2net_applied=net2net_applied)
                self.static_ges.append(ge)

                ck_config.set_index(index=i)
                print(f"\t--- Training graph {i} ---")
                training_time = self._train_model(dy_ge_idx=i, filepath=join(folder_path, f"graph_{i}"),
                                                  batch_size=batch_size, epochs=epochs, learning_rate=learning_rate,
                                                  skip_print=skip_print, early_stop=early_stop, plot_loss=plot_loss,
                                                  ck_config=ck_config)
                print(f"Training time in {training_time}s")

        # else:
        #     # Check dyn_ge has model?
        #     if len(self.static_ges) == 0:
        #         self.load_models(folder_path=folder_path)
        #
        #     if model_index is not None:
        #         if model_index >= len(self.static_ges):
        #             raise ValueError("Model_index is invalid!")
        #
        #         if model_index > 0:
        #             graph = nx.Graph(self.graphs[model_index])
        #             input_dim = len(graph.nodes())
        #             prev_model = load_custom_model(filepath=join(folder_path, f"graph_{model_index - 1}"))
        #             curr_model = handle_expand_model(model=prev_model, input_dim=input_dim,
        #                                              prop_size=prop_size, net2net_applied=net2net_applied)
        #
        #             ge = TStaticGE(G=graph, model=curr_model, alpha=self.alpha, beta=self.beta)
        #             self.static_ges[model_index] = ge
        #
        #         if checkpoint_config is not None:
        #             ck_config = deepcopy(checkpoint_config)
        #             ck_config.Index = model_index
        #         print(f"---* Training graph at Index = {model_index} ---")
        #         start_time = time()
        #
        #         self.static_ges[model_index].train(batch_size=batch_size, epochs=epochs, skip_print=skip_print,
        #                                            learning_rate=learning_rate, ck_config=ck_config,
        #                                            early_stop=early_stop, plot_loss=plot_loss)
        #         print(f"Training time in {round(time() - start_time, 2)}s")
        #         save_custom_model(model=self.static_ges[model_index].get_model(),
        #                           filepath=join(folder_path, f"graph_{model_index}"))
        #     else:
        #         for i in range(len(self.graphs)):
        #             if checkpoint_config is not None:
        #                 ck_config = deepcopy(checkpoint_config)
        #                 ck_config.Index = i
        #             print(f"--- Training graph {i} ---")
        #             start_time = time()
        #
        #             self.static_ges[i].train(batch_size=batch_size, epochs=epochs, skip_print=skip_print,
        #                                      learning_rate=learning_rate, ck_config=ck_config, early_stop=early_stop,
        #                                      plot_loss=plot_loss)
        #             print(f"Training time in {round(time() - start_time, 2)}s")
        #             save_custom_model(model=self.static_ges[i].get_model(), filepath=join(folder_path, f"graph_{i}"))

    def load_models(self, folder_path):
        print("Loading models...", end=" ")
        start_time = time()
        self.static_ges = []

        # Trick for get length of saved models
        files = [f for f in listdir(folder_path) if isfile(join(folder_path, f))]
        length = int(len(files) / 2)

        for i in range(length):
            filepath = join(folder_path, f"graph_{i}")
            model = load_custom_model(filepath=filepath)

            ge = TStaticGE(G=self.graphs[i], model=model, alpha=self.alpha, beta=self.beta)
            self.static_ges.append(ge)
        print(f"{round(time() - start_time, 2)}s")


if __name__ == "__main__":
    g1 = nx.gnm_random_graph(n=5, m=5, seed=6)
    g2 = nx.gnm_random_graph(n=8, m=12, seed=6)
    g3 = nx.gnm_random_graph(n=13, m=20, seed=6)
    graphs = [g1, g2, g3]

    ck_config = CheckpointConfig(number_saved=10, folder_path="../models/generate_ck")

    # graphs, _ = read_dynamic_graph(folder_path="../data/fb", convert_to_idx=True, limit=1)

    dy_ge = TDynGE(graphs=graphs, embedding_dim=2)
    # dy_ge.load_models(folder_path="../models/generate")
    dy_ge.train(prop_size=0.4, epochs=1000, skip_print=100, net2net_applied=False, learning_rate=0.003,
                folder_path="../models/generate/", from_loaded_model=False, ck_config=ck_config,
                early_stop=50, plot_loss=True)

    # dy_ge.train(prop_size=0.4, epochs=100, skip_print=5, net2net_applied=False, learning_rate=0.003,
    #             folder_path="../models/generate/", from_loaded_model=False, checkpoint_config=checkpoint_config, early_stop=50)

    print("Show embedding:")
    embeddings_list = dy_ge.get_all_embeddings()
    # for e in embeddings_list:
    #     plot_embedding(embeddings=e)
