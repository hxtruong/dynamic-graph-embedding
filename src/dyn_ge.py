from os.path import join, exists
import os
from time import time
import networkx as nx
import torch
from torch.autograd import Variable

from src.data_preprocessing.graph_preprocessing import read_dynamic_graph
from src.static_ge import TStaticGE
from src.utils.autoencoder import TAutoencoder
from src.utils.model_utils import get_hidden_layer, handle_expand_model, save_custom_model, load_custom_model
from src.utils.visualize import plot_embedding


class TDynGE(object):
    def __init__(self, graphs, embedding_dim, l1=0.001, l2=0.001):
        super(TDynGE, self).__init__()
        if not graphs:
            raise ValueError("Must be provide graphs data")

        self.graphs = graphs
        self.graph_len = len(graphs)
        self.embedding_dim = embedding_dim
        self.l1 = l1
        self.l2 = l2
        self.static_ges = []
        self.model_folder_paths = []

    def get_all_embeddings(self):
        return [ge.get_embedding() for ge in self.static_ges]

    def get_embedding(self, index):
        if index < 0 or index >= self.graph_len:
            raise ValueError("index is invalid!")
        return self.static_ges[index].get_embedding()

    def train(self, prop_size=0.4, batch_size=64, epochs=100, folder_path="../models/generate/", skip_print=5,
              net2net_applied=False, learning_rate=0.001, save_model_point=None, from_loaded_model=False):
        if not from_loaded_model:
            init_hidden_dims = get_hidden_layer(prop_size=prop_size, input_dim=len(self.graphs[0].nodes()),
                                                embedding_dim=self.embedding_dim)
            if not exists(folder_path):
                os.makedirs(folder_path)

            model = TAutoencoder(
                input_dim=len(self.graphs[0].nodes()),
                embedding_dim=self.embedding_dim,
                hidden_dims=init_hidden_dims,
                l1=self.l1,
                l2=self.l2
            )
            ge = TStaticGE(G=self.graphs[0], model=model)
            print(f"--- Training graph {0} ---")
            start_time = time()
            ge.train(batch_size=batch_size, epochs=epochs, skip_print=skip_print, learning_rate=learning_rate)
            print(f"Training time in {round(time() - start_time, 2)}s")

            self.static_ges.append(ge)
            save_custom_model(model=model, filepath=join(folder_path, "graph_0"))

            for i in range(1, len(self.graphs)):
                graph = nx.Graph(self.graphs[i])
                input_dim = len(graph.nodes())
                prev_model = load_custom_model(filepath=join(folder_path, f"graph_{i - 1}"))
                curr_model = handle_expand_model(model=prev_model, input_dim=input_dim,
                                                 prop_size=prop_size, net2net_applied=net2net_applied)

                ge = TStaticGE(G=graph, model=curr_model)

                print(f"--- Training graph {i} ---")
                start_time = time()
                ge.train(batch_size=batch_size, epochs=epochs, skip_print=skip_print, learning_rate=learning_rate)
                print(f"Training time in {round(time() - start_time, 2)}s")

                self.static_ges.append(ge)
                save_custom_model(model=curr_model, filepath=join(folder_path, f"graph_{i}"))
        else:
            for i in range(len(self.graphs)):
                print(f"--- Training graph {i} ---")
                start_time = time()

                self.static_ges[i].train(batch_size=batch_size, epochs=epochs, skip_print=skip_print,
                                         learning_rate=learning_rate)
                print(f"Training time in {round(time() - start_time, 2)}s")

                save_custom_model(model=self.static_ges[i].get_model(), filepath=join(folder_path, f"graph_{i}"))

    def load_models(self, folder_path):
        print("Loading models...", end=" ")
        start_time = time()
        model_folders_paths = os.listdir(folder_path)
        self.model_folder_paths = []
        self.static_ges = []
        for i in range(len(self.graphs)):
            filepath = join(folder_path, f"graph_{i}")
            model = load_custom_model(filepath=filepath)

            ge = TStaticGE(G=self.graphs[i], model=model)
            self.static_ges.append(ge)
        print(f"{round(time() - start_time, 2)}s")


if __name__ == "__main__":
    g1 = nx.gnm_random_graph(n=10, m=15, seed=6)
    g2 = nx.gnm_random_graph(n=15, m=40, seed=6)
    g3 = nx.gnm_random_graph(n=20, m=50, seed=6)
    graphs = [g1, g2, g3]

    # graphs, _ = read_dynamic_graph(folder_path="../data/fb", convert_to_idx=True, limit=1)

    dy_ge = TDynGE(graphs=graphs, embedding_dim=4)
    # dy_ge.load_models(folder_path="../models/generate")
    # dy_ge.train(prop_size=0.4, epochs=10, skip_print=2, net2net_applied=False, learning_rate=0.0005,
    #             folder_path="../models/generate/", save_model_point=None, from_loaded_model=True)

    dy_ge.train(prop_size=0.4, epochs=10, skip_print=2, net2net_applied=False, learning_rate=0.003,
                folder_path="../models/generate/", save_model_point=None, from_loaded_model=False)

    print("Show embedding:")
    embeddings_list = dy_ge.get_all_embeddings()
    for e in embeddings_list:
        plot_embedding(embeddings=e)
