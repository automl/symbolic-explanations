import pandas as pd
import os
import shutil
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from itertools import combinations

from utils.functions_utils import get_functions2d, NamedFunction
from utils.model_utils import get_hyperparams, get_classifier_from_run_conf
from utils.logging_utils import get_logger


if __name__ == "__main__":
    symb_dir_name = "default"
    functions = get_functions2d()
    #models = ["MLP", "SVM", "BDT", "DT"]
    models = functions
    data_sets = ["digits", "iris"]

    run_configs = []
    for model in models:
        if isinstance(model, NamedFunction):
            run_configs.append({"model": model, "data_set_name": None})
        else:
            hyperparams = get_hyperparams(model_name=model)
            hp_comb = combinations(hyperparams, 2)
            for hp_conf in hp_comb:
                for ds in data_sets:
                    run_configs.append({"model": model, hp_conf[0]: True, hp_conf[1]: True, "data_set_name": ds})

    # Set up plot directories
    plot_dir = f"learning_curves/plots/combined_plots"
    complexity_plot_dir = f"{plot_dir}/complexity"
    mse_plot_dir = f"{plot_dir}/mse"
    rmse_plot_dir = f"{plot_dir}/rmse"
    kt_plot_dir = f"{plot_dir}/kt"
    if os.path.exists(plot_dir):
        shutil.rmtree(plot_dir)
    os.makedirs(complexity_plot_dir)
    os.makedirs(mse_plot_dir)
    os.makedirs(rmse_plot_dir)
    os.makedirs(kt_plot_dir)

    logger = get_logger(filename=f"{plot_dir}/plot_log.log")

    logger.info(f"Save plots to {plot_dir}.")

    for run_conf in run_configs:

        if run_conf['data_set_name']:
            data_set = run_conf['data_set_name']
            data_set_postfix = f"_{run_conf['data_set_name']}"
        else:
            data_set = None
            data_set_postfix = ""
        model = run_conf.pop("model")
        if isinstance(model, NamedFunction):
            classifier = model
        else:
            classifier = get_classifier_from_run_conf(model_name=model, run_conf=run_conf)

        function_name = classifier.name if isinstance(classifier, NamedFunction) else model
        optimized_parameters = classifier.configspace.get_hyperparameters()
        parameter_names = [param.name for param in optimized_parameters]

        run_name = f"{function_name.replace(' ', '_')}_{'_'.join(parameter_names)}{data_set_postfix}"

        logger.info(f"Create plot for {run_name}.")

        # Load test data
        logger.info(f"Get test data.")
        X_test = np.array(pd.read_csv(f"learning_curves/runs_symb/{symb_dir_name}/smac/{run_name}/x_test.csv", header=False))
        y_test = np.array(pd.read_csv(f"learning_curves/runs_symb/{symb_dir_name}/smac/{run_name}/y_test.csv"))

        avg_cost = y_test.mean()
        std_cost = y_test.std()

        df_error_metrics_all = pd.DataFrame()
        df_complexity_all = pd.DataFrame()

        for sampling_type in ["Symbolic Regression (Random Sampling)", "Symbolic Regression (BO Sampling)", "Gaussian Process (BO Sampling)"]:

            if sampling_type == "Symbolic Regression (BO Sampling)":
                symb_dir = f"learning_curves/runs_symb/{symb_dir_name}/smac/{run_name}"
            elif sampling_type == "Gaussian Process (BO Sampling)":
                symb_dir = f"learning_curves/runs_surr/{run_name}"
            else:
                symb_dir = f"learning_curves/runs_symb/{symb_dir_name}/rand/{run_name}"

            if sampling_type == "Gaussian Process (BO Sampling)":
                df_error_metrics = pd.read_csv(f"{symb_dir}/surrogate_error_metrics.csv")
            else:
                df_error_metrics = pd.read_csv(f"{symb_dir}/error_metrics.csv")
                df_complexity = pd.read_csv(f"{symb_dir}/complexity.csv")
                df_complexity.insert(0, "Experiment", f"{sampling_type}")
                df_complexity_all = pd.concat((df_complexity_all, df_complexity))

            df_error_metrics["rmse_test_smac"] = np.sqrt(df_error_metrics["mse_test_smac"])
            df_error_metrics["rmse_train_smac"] = np.sqrt(df_error_metrics["mse_train_smac"])
            df_error_metrics.insert(0, "Experiment", f"{sampling_type}")
            df_error_metrics_all = pd.concat((df_error_metrics_all, df_error_metrics))

        logger.info(f"Create plots.")

        classifier_titles = {
            "BDT": "Boosted Decision Tree",
            "DT": "Decision Tree",
            "SVM": "Support Vector Machine",
            "MLP": "Neural Network",
        }
        if classifier.name in classifier_titles.keys():
            classifier_title = classifier_titles[classifier.name]
        else:
            classifier_title = classifier.name

        param0 = f"log({optimized_parameters[0].name})" if optimized_parameters[0].log else optimized_parameters[0].name
        param1 = f"log({optimized_parameters[1].name})" if optimized_parameters[1].log else optimized_parameters[1].name

        # Plot RMSE
        plt.figure()
        _, ax = plt.subplots(figsize=(8, 5))
        line = plt.axhline(y=std_cost, color='darkred', linestyle='--', linewidth=0.5, label="Test Standard Deviation")
        sns.pointplot(data=df_error_metrics_all, x="n_samples", y="rmse_test_smac", hue="Experiment", errorbar="sd",
                      linestyles="", capsize=0.2, errwidth=0.7, scale=0.7, dodge=0.4)#, showfliers=False)
        if data_set:
            plt.title(f"{classifier_title}, Dataset: {data_set}\nOptimize: {param0}, {param1}", fontsize=16)
        else:
            plt.title(f"{classifier_title}\nOptimize: {param0}, {param1}", fontsize=16)
        #plt.title(f"Test Mean: {avg_cost:.3f}, Test Std.: {std_cost:.3f}", fontsize=10),
        plt.ylabel("Test RMSE", fontsize=16)
        plt.yticks(fontsize=14)
        plt.xlabel("Number of Samples", fontsize=16)
        plt.xticks(fontsize=14)
        plt.ylim(0., 0.32)
        plt.tight_layout(rect=(0, 0.05, 1, 1))
        sns.move_legend(
            ax, "lower center",
            bbox_to_anchor=(0.45, -0.3),
            ncol=4,
            title=None, frameon=False,
            fontsize=16
        )
        plt.savefig(f"{rmse_plot_dir}/{run_name}_pointplot.png", dpi=400)


        # Plot Kendall
        plt.figure()
        _, ax = plt.subplots(figsize=(8, 5))
        sns.pointplot(data=df_error_metrics_all, x="n_samples", y="kt_test_smac", hue="Experiment", errorbar="sd",
                      linestyles="", capsize=0.2, errwidth=0.7, scale=0.7, dodge=0.4)#, showfliers=False)
        if data_set:
            plt.title(f"{classifier_title}, Dataset: {data_set}\nOptimize: {param0}, {param1}", fontsize=16)
        else:
            plt.title(f"{classifier_title}\nOptimize: {param0}, {param1}", fontsize=16)
        plt.ylabel("Test Kendall Tau", fontsize=16)
        plt.yticks(fontsize=14)
        plt.xlabel("Number of Samples", fontsize=16)
        plt.xticks(fontsize=14)
        plt.tight_layout(rect=(0, 0.05, 1, 1))
        sns.move_legend(
            ax, "lower center",
            bbox_to_anchor=(0.45, -0.24),
            ncol=4,
            title=None, frameon=False,
        )
        plt.savefig(f"{kt_plot_dir}/{run_name}_pointplot.png", dpi=400)

        # Plot Complexity
        plt.figure()
        _, ax = plt.subplots(figsize=(8, 5))
        sns.pointplot(data=df_complexity_all, x="n_samples", y="program_operations", hue="Experiment", errorbar="sd",
                      linestyles="", capsize=0.2, errwidth=0.7, scale=0.7, dodge=0.2)#, showfliers=False)
        if data_set:
            plt.title(f"{classifier_title}, Dataset: {data_set}\nOptimize: {param0}, {param1}", fontsize=16)
        else:
            plt.title(f"{classifier_title}\nOptimize: {param0}, {param1}", fontsize=16)
        plt.ylabel("Number of Operations in Formula", fontsize=16)
        plt.yticks(np.arange(0, 20, 2.0), fontsize=14)
        plt.xlabel("Number of Samples", fontsize=16)
        plt.xticks(fontsize=14)
        plt.ylim(0, 18.5)
        plt.tight_layout(rect=(0, 0.05, 1, 1))
        sns.move_legend(
            ax, "lower center",
            bbox_to_anchor=(0.45, -0.24),
            ncol=2,
            title=None, frameon=False,
        )
        plt.savefig(f"{complexity_plot_dir}/{run_name}_complexity_pointplot.png", dpi=400)

