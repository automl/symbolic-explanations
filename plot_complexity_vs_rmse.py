import pandas as pd
import os
import shutil
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import argparse

from utils.logging_utils import get_logger
from utils.hpobench_utils import get_run_config, get_benchmark_dict, get_task_dict

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--job_id')
    args = parser.parse_args()

    parsimony_coefficient_space = [
        0.0001
    ]
    # parsimony_coefficient_space = [
    #     0.0001, 0.00025, 0.0005, 0.00075,
    #     0.001, 0.0025, 0.005, 0.0075,
    #     0.01, 0.025, 0.05, 0.075
    # ]

    # number of HPs to optimize
    n_optimized_params = 2
    # number of HP combinations to consider per model
    max_hp_comb = 1

    n_samples = 200
    labelsize = 16
    titlesize=18

    if args.job_id:
        run_configs = [
            get_run_config(job_id=args.job_id, n_optimized_params=n_optimized_params, max_hp_comb=max_hp_comb)]
    else:
        run_configs = get_run_config(n_optimized_params=n_optimized_params, max_hp_comb=max_hp_comb)

    # Set up plot directories
    plot_dir = f"results/plots/complexity_vs_rmse_hpobench"
    if os.path.exists(plot_dir):
        shutil.rmtree(plot_dir)
    os.makedirs(plot_dir)

    logger = get_logger(filename=f"{plot_dir}/plot_log.log")

    logger.info(f"Save plots to {plot_dir}.")

    fig = plt.figure(figsize=(15, 8))

    for i, run_conf in enumerate(run_configs):
        task_dict = get_task_dict()
        data_set = f"{task_dict[run_conf['task_id']]}"
        optimized_parameters = list(run_conf["hp_conf"])
        model_name = get_benchmark_dict()[run_conf["benchmark"]]
        b = run_conf["benchmark"](task_id=run_conf["task_id"], hyperparameters=optimized_parameters)

        # add only parameters to be optimized to configspace
        cs = b.get_configuration_space(hyperparameters=optimized_parameters)

        run_name = f"{model_name.replace(' ', '_')}_{'_'.join(optimized_parameters)}_{data_set}"

        logger.info(f"########## Create plot for {run_name}.")

        df_joined_all = pd.DataFrame()

        for parsimony in parsimony_coefficient_space:

            logger.info(f"#### Evaluate parsimony {parsimony}")

            symb_dir = f"results/runs_symb_hpobench/parsimony{parsimony}/surr/{run_name}"

            try:
                df_error_metrics = pd.read_csv(f"{symb_dir}/error_metrics.csv")
                df_error_metrics["rmse_test"] = np.sqrt(df_error_metrics["mse_test"])
                df_error_metrics["rmse_train"] = np.sqrt(df_error_metrics["mse_train"])
                df_error_metrics = df_error_metrics[df_error_metrics["n_samples"] == n_samples]

                logger.info(f"Number of SR evaluations found: {len(df_error_metrics)}")

                df_complexity = pd.read_csv(f"{symb_dir}/complexity.csv")
                df_complexity = df_complexity[df_complexity["n_samples"] == n_samples]
                logger.info(f"Number of times complexity == -1: {len(df_complexity[df_complexity['program_operations'] == -1])}")
                df_complexity = df_complexity[df_complexity["program_operations"] != -1]

                df_joined = pd.DataFrame({
                    "rmse_test": [df_error_metrics["rmse_test"].mean(axis=0)],
                    "complexity": [df_complexity["program_operations"].mean(axis=0)]
                })
                df_joined.insert(0, "Parsimony", parsimony)
                df_joined_all = pd.concat((df_joined_all, df_joined))
            except Exception as e:
                logger.warning(f"Could not process parsimony {parsimony} for {run_name}: \n{e}")

        if df_joined_all.empty:
            logger.warning(f"Could not create plot for {run_name} as no parsimony could be processed.")
            continue
        df_joined_all['Parsimony'] = df_joined_all['Parsimony'].astype(str)
        df_joined_all.to_csv(f"{plot_dir}/df_joined_all_{run_name}")

        g = sns.scatterplot(data=df_joined_all, x="complexity", y="rmse_test", hue="Parsimony",
                            linestyles="", s=80, palette="cividis")
        if model_name == "LR":
            classifier_title = "Logistic Regression"
        else:
            classifier_title = model_name
        plt.title(f"Dataset: {data_set}\n{classifier_title} ({', '.join(optimized_parameters)})", fontsize=titlesize)
        plt.xlabel("Operation Count", fontsize=labelsize, labelpad=10)
        plt.ylabel("RMSE $(c, s)$", fontsize=labelsize, labelpad=14)
        plt.yticks(fontsize=labelsize-2)
        plt.xticks(fontsize=labelsize-2)
        legend = plt.legend(loc='center right', title="Parsimony", frameon=False, fontsize=titlesize)
        legend.get_title().set_fontsize(titlesize)

        plt.tight_layout()
        plt.savefig(f"{plot_dir}/pointplot.png", dpi=400)
        plt.close()
