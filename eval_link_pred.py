import warnings

import networkx as nx

from src.data_preprocessing.graph_preprocessing import read_dynamic_graph
from src.utils.config_file import read_config_file
from src.utils.data_utils import load_single_processed_data, load_dy_embeddings, load_node2vec_embeddings
from src.utils.graph_util import print_graph_stats
from src.utils.precision_k_evaluate import check_link_predictionK
from src.utils.model_training_utils import link_pred_eva
from src.utils.setting_param import SettingParam

warnings.filterwarnings("ignore")

if __name__ == "__main__":
    # dataset_name = "soc_wiki"
    # params = {
    #     # 'algorithm': {
    #     'is_dyge': True,
    #     'is_node2vec': True,
    #     'is_sdne': True,
    #
    #     # 'folder_paths': {
    #     'dataset_folder': f"./data/{dataset_name}",
    #     'processed_link_pred_data_folder': f"./saved_data/processed_data/{dataset_name}_link_pred",
    #
    #     'dyge_emb_folder': f"./saved_data/embeddings/{dataset_name}_link_pred",
    #     'node2vec_emb_folder': f"./saved_data/node2vec_emb/{dataset_name}_link_pred",
    #     'sdne_emb_folder': f"./saved_data/sdne_emb/{dataset_name}_link_pred",
    # }
    # params = SettingParam(**params)

    params = read_config_file(filepath="./link_pred_configuration.ini", config_task="link_pred")
    is_mAP_eval = False
    # ==================== Data =========================
    graphs, idx2node = read_dynamic_graph(
        folder_path=params.dataset_folder,
        limit=None,
        convert_to_idx=True
    )

    print("Origin graphs:")
    for i, g in enumerate(graphs):
        print_graph_stats(g, i, end="\t")
        print(f"Isolate nodes: {nx.number_of_isolates(g)}")
        # draw_graph(g, limit_node=25)
    # =================== Processing data for link prediction ==========================
    print("Load processed data from disk...")
    g_hidden_df, g_hidden_partial = load_single_processed_data(folder=params.processed_link_pred_data_folder)

    # Set last graph in dynamic graph is hidden graph
    orginial_graph = graphs[-1]
    graphs[-1] = g_hidden_partial

    print("After processing for link prediction graphs:")
    for i, g in enumerate(graphs):
        print_graph_stats(g, i, end="\t")
        print(f"Isolate nodes: {nx.number_of_isolates(g)}")

    # ========= DynGEM ===========
    if params.is_dyge:
        print("=============== DynGEM ============")
        # -------- Training ----------
        dy_embeddings = load_dy_embeddings(params.dyge_emb_folder, index=len(graphs) - 1)
        link_pred_eva(g_hidden_df=g_hidden_df, hidden_dy_embedding=dy_embeddings[-1])
        if is_mAP_eval:
            k_query_res, AP = check_link_predictionK(embedding=dy_embeddings[-1], train_graph=g_hidden_partial,
                                                     origin_graph=orginial_graph,
                                                     k_query=[
                                                         2, 10,
                                                         100, 200, 1000, 10000
                                                     ])
            print(f"mAP = {AP}")
    # ============== Node2Vec ============
    if params.is_node2vec:
        print("=============== Node2vec ============")
        # Just need train last graph
        dy_embeddings = load_node2vec_embeddings(graphs, folder_path=params.node2vec_emb_folder, index=len(graphs) - 1)
        link_pred_eva(g_hidden_df=g_hidden_df, hidden_dy_embedding=dy_embeddings[-1])

        if is_mAP_eval:
            k_query_res, AP = check_link_predictionK(embedding=dy_embeddings[-1], train_graph=g_hidden_partial,
                                                     origin_graph=orginial_graph,
                                                     k_query=[
                                                         2, 10,
                                                         100, 200, 1000, 10000
                                                     ])
            print(f"mAP = {AP}")

    # ==================== SDNE ===============
    if params.is_sdne:
        print("=============== SDNE ============")
        dy_embeddings = load_dy_embeddings(folder_path=params.sdne_emb_folder, index=len(graphs) - 1)

        link_pred_eva(g_hidden_df=g_hidden_df, hidden_dy_embedding=dy_embeddings[0])
        if is_mAP_eval:
            k_query_res, AP = check_link_predictionK(embedding=dy_embeddings[-1], train_graph=g_hidden_partial,
                                                     origin_graph=orginial_graph,
                                                     k_query=[
                                                         2, 10,
                                                         100, 200, 1000, 10000
                                                     ])
            print(f"mAP = {AP}")
