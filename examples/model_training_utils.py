import os
import warnings
from operator import itemgetter
from os.path import join
from time import time

import numpy as np
from node2vec import Node2Vec

from src.utils.checkpoint_config import CheckpointConfig
from src.utils.setting_param import SettingParam

warnings.filterwarnings("ignore")

from src.dyn_ge import TDynGE
from src.utils.link_prediction import run_link_pred_evaluate


def create_dump_models(dy_ge: TDynGE, weight_model_folder):
    '''
    Method to create saved model on disk for later optimizer
    :return:
    '''
    dy_ge.train(epochs=1, skip_print=1, learning_rate=1e-6,
                folder_path=weight_model_folder)


def train_model(dy_ge: TDynGE, params: SettingParam):
    print("\n-----------\nStart total training...")

    print("Creating model saving for each graph...")
    create_dump_models(dy_ge, weight_model_folder=params.dyge_weight_folder)

    print("\n### ==\tOptimize model training == ###")

    start_time_train = time()
    for model_idx in range(dy_ge.size):
        print(f"\n==========\t Model index = {model_idx} ============")
        for i, lr in enumerate(params.learning_rate_list):
            is_load_from_previous_model = False
            if i == 0:
                is_load_from_previous_model = True  # Always create from previous model if start training
            print("\tLearning rate = ", lr)
            dy_ge.train_at(model_index=model_idx,
                           learning_rate=lr,
                           prop_size=params.prop_size, epochs=params.epochs, skip_print=params.skip_print,
                           net2net_applied=params.net2net_applied,
                           batch_size=params.batch_size, folder_path=params.dyge_weight_folder,
                           ck_config=CheckpointConfig(number_saved=params.ck_length_saving,
                                                      folder_path=params.ck_folder),
                           early_stop=params.early_stop,
                           is_load_from_previous_model=is_load_from_previous_model)

    print(f"\nFinish total training: {round(time() - start_time_train, 2)}s\n--------------\n")


def train_model_at_index(dy_ge: TDynGE, params: SettingParam):
    '''
    TODO: Should support for resuming train which continue train with learning_rate
    :return:
    '''
    print(f"\n==========\t Model index = {params.specific_dyge_model_index} ============")
    start_time_train = time()
    for i, lr in enumerate(params.learning_rate_list):
        is_load_from_previous_model = False
        if i == 0:
            is_load_from_previous_model = True  # Prevent re-train model
        print("\tLearning rate = ", lr)
        dy_ge.train_at(model_index=params.specific_dyge_model_index,
                       learning_rate=lr,
                       prop_size=params.prop_size, epochs=params.epochs, skip_print=params.skip_print,
                       net2net_applied=params.net2net_applied,
                       batch_size=params.batch_size, folder_path=params.dyge_weight_folder,
                       ck_config=CheckpointConfig(number_saved=params.ck_length_saving,
                                                  folder_path=params.ck_folder),
                       early_stop=params.early_stop,
                       is_load_from_previous_model=is_load_from_previous_model)

    print(f"\nFinish total training: {round(time() - start_time_train, 2)}s\n--------------\n")


def check_current_loss_model(dy_ge: TDynGE, weight_model_folder):
    for model_idx in range(dy_ge.size):
        dy_ge.train_at(model_index=model_idx, folder_path=weight_model_folder,
                       epochs=1, learning_rate=1e-7,
                       is_load_from_previous_model=False)


def dyngem_alg(graphs, params: SettingParam):
    # ----------- Training area -----------
    dy_ge = TDynGE(
        graphs=graphs, embedding_dim=params.embedding_dim,
        alpha=params.alpha, beta=params.beta, l1=params.l1, l2=params.l2
    )
    if params.is_load_dyge_model:
        print("\n-----------\nStart load model...")
        dy_ge.load_models(folder_path=params.dyge_weight_folder)
    elif params.specific_dyge_model_index is not None:
        train_model_at_index(dy_ge, params)
    else:
        train_model(dy_ge, params=params)

    # Uncomment to know current loss value
    print("Check current loss model")
    check_current_loss_model(dy_ge, weight_model_folder=params.dyge_weight_folder)

    print("Saving embeddings...")
    dy_ge.save_embeddings(folder_path=params.dyge_emb_folder)

    # print("Loading embedding...")
    # dy_embeddings = dy_ge.load_embeddings(folder_path=embeddings_folder)
    dy_embeddings = dy_ge.get_all_embeddings()
    # print(np.array_equal(dy_embeddings, dyn))

    return dy_ge, dy_embeddings


def _node2vec_alg(graph, embedding_dim, filename=None, is_load_emb=False):
    node2vec = Node2Vec(graph=graph,
                        dimensions=embedding_dim,
                        walk_length=80,
                        num_walks=20,
                        workers=2)  # Use temp_folder for big graphs
    node2vec_model = node2vec.fit()
    if is_load_emb:
        embedding = node2vec_model.wv.load_word2vec_format(filename)
    else:
        embedding = [np.array(node2vec_model[str(u)]) for u in sorted(graph.nodes)]
        if filename is not None:
            node2vec_model.wv.save_word2vec_format(filename)

    return np.array(embedding)


def node2vec_alg(graphs, embedding_dim, index=None, folder_path=None, is_load_emb=False):
    dy_embeddings = []
    # TODO: set is_load_emb
    is_load_emb = False
    if index is not None and index < len(graphs):
        return _node2vec_alg(graphs[index], embedding_dim=embedding_dim, filename=join(folder_path, "n2v_emb"),
                             is_load_emb=is_load_emb)
    for idx, g in enumerate(graphs):
        embedding = _node2vec_alg(graph=g, embedding_dim=embedding_dim,
                                  filename=join(folder_path, f"n2v_emb{idx}"), is_load_emb=is_load_emb)
        dy_embeddings.append(embedding)
    dy_embeddings = np.array(dy_embeddings)
    return dy_embeddings


def link_pred_eva(g_hidden_df, hidden_dy_embedding):
    # ----- run evaluate link prediction -------

    print(f"\n-->Run link predict evaluation ---")
    link_pred_model = run_link_pred_evaluate(
        graph_df=g_hidden_df,
        embeddings=hidden_dy_embedding,
        num_boost_round=20000
    )
    possible_edges_df = g_hidden_df[g_hidden_df['link'] == 0]
    # y_pred = run_predict(data=possible_edges_df, embedding=hidden_dy_embedding, model=link_pred_model)
    # top_k_edges = top_k_prediction_edges(
    #     G=g_hidden_partial, y_pred=y_pred, possible_edges_df=possible_edges_df,
    #     top_k=top_k, show_acc_on_edge=show_acc_on_edge,
    #     plot_link_pred=False, limit_node=25
    # )


def create_folder(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
