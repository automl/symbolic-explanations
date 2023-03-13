import pandas as pd
import os
import sys
import numpy as np
import dill as pickle
from itertools import combinations

from utils.utils import get_hpo_test_data, plot_symb2d, get_surrogate_predictions, convert_symb
from utils.functions_utils import get_functions2d, NamedFunction
from utils.model_utils import get_hyperparams, get_classifier_from_run_conf
from utils import functions_utils
from utils.logging_utils import get_logger

sys.modules['functions'] = functions_utils

N_SAMPLES_SPACING = np.linspace(20, 200, 10, dtype=int).tolist()

if __name__ == "__main__":
    n_samples = 100
    n_test_samples = 100
    symb_dir_name = "default"
    functions = get_functions2d()
    models = ["MLP", "SVM", "BDT", "DT"]
    # models = functions
    data_sets = ["digits", "iris"]
    evaluate_on_surrogate = True

    init_design_max_ratio = 0.25
    init_design_n_configs_per_hyperparamter = 8

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

    # set up directories
    plot_dir = f"learning_curves/plots"
    viz_plot_dir = f"{plot_dir}/visualization_error"
    if not os.path.exists(viz_plot_dir):
        os.makedirs(viz_plot_dir)

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

        sampling_dir_smac = f"learning_curves/runs_sampling/smac/{run_name}"
        sampling_dir_rand = f"learning_curves/runs_sampling/rand/{run_name}"

        symb_dir_surr = f"learning_curves/runs_symb/{symb_dir_name}/surr/{run_name}/symb_models"
        symb_dir_smac = f"learning_curves/runs_symb/{symb_dir_name}/smac/{run_name}/symb_models"
        symb_dir_rand = f"learning_curves/runs_symb/{symb_dir_name}/rand/{run_name}/symb_models"

        with open(f"{sampling_dir_smac}/classifier.pkl", "rb") as classifier_file:
            classifier = pickle.load(classifier_file)
        if isinstance(classifier, NamedFunction):
            classifier_name = classifier.name
        else:
            classifier_name = classifier.name
        optimized_parameters = classifier.configspace.get_hyperparameters()
        parameter_names = [param.name for param in optimized_parameters]

        if init_design_max_ratio * n_samples < len(
                optimized_parameters) * init_design_n_configs_per_hyperparamter:
            n_eval = n_samples
        else:
            n_eval = max(N_SAMPLES_SPACING)
        df_samples_smac = pd.read_csv(f"{sampling_dir_smac}/samples_{n_eval}.csv")
        df_samples_rand = pd.read_csv(f"{sampling_dir_rand}/samples_{max(N_SAMPLES_SPACING)}.csv")

        # Load test data
        logger.info(f"Get test data for {classifier_name}.")
        try:
            X_test = get_hpo_test_data(classifier, optimized_parameters, n_test_samples, return_x=True)
            y_test = np.array(
                pd.read_csv(f"learning_curves/runs_symb/default/smac/{run_name}/y_test.csv", header=None))
            y_test = y_test.reshape(X_test.shape[1], X_test.shape[2])
        except:
            logger.info(f"No test data found, create test data for {run_name}.")
            X_test, y_test = get_hpo_test_data(classifier, optimized_parameters, n_test_samples)

        df_error_metrics_smac = pd.read_csv(f"learning_curves/runs_symb/{symb_dir_name}/smac/{run_name}/error_metrics.csv")

        n_seeds_total = 0
        error_test = {}
        if evaluate_on_surrogate:
            error_test[f"SR (BO-GP)"] = 0
            error_test["GP (BO)"] = 0
        else:
            error_test[f"SR (BO)"] = 0
            error_test[f"SR (Random)"] = 0

        for sampling_seed in df_samples_smac.seed.unique():
            logger.info(f"Considering sampling seed {sampling_seed}.")
            df_sampling_seed_smac = df_samples_smac.copy()[df_samples_smac["seed"] == sampling_seed]
            df_sampling_seed_rand = df_samples_rand.copy()[df_samples_rand["seed"] == sampling_seed]

            X_train_smac = np.array(df_sampling_seed_smac[[parameter_names[0], parameter_names[1]]])[:n_samples]
            X_train_rand = np.array(df_sampling_seed_rand[[parameter_names[0], parameter_names[1]]])[:n_samples]

            for symb_seed in df_error_metrics_smac.symb_seed.unique():
                logger.info(f"Considering symb seed {symb_seed}.")

                n_seeds_total += 1

                if evaluate_on_surrogate:
                    with open(
                            f"{symb_dir_surr}/n_samples{n_samples}_sampling_seed{sampling_seed}_symb_seed{symb_seed}.pkl",
                            "rb") as symb_model_file_surr:
                        symb_surr = pickle.load(symb_model_file_surr)
                    symb_pred_surr = symb_surr.predict(
                        X_test.T.reshape(X_test.shape[1] * X_test.shape[2], X_test.shape[0])
                    ).reshape(X_test.shape[2], X_test.shape[1]).T
                    error_test[f"SR (BO-GP)"] += np.abs(y_test - symb_pred_surr)

                    surr_dir = f"learning_curves/runs_surr/{run_name}"
                    with open(
                            f"{sampling_dir_smac}/surrogates/n_eval{n_eval}_samples{n_samples}_seed{sampling_seed}.pkl",
                            "rb") as surrogate_file:
                        surrogate_model = pickle.load(surrogate_file)
                    error_test["GP (BO)"] += np.abs(y_test - np.array(get_surrogate_predictions(
                        X_test.reshape(len(optimized_parameters), -1).T, classifier, surrogate_model)).reshape(
                        X_test.shape[1], X_test.shape[2]))
                else:
                    with open(
                            f"{symb_dir_smac}/n_samples{n_samples}_sampling_seed{sampling_seed}_symb_seed{symb_seed}.pkl",
                            "rb") as symb_model_file_smac:
                        symb_smac = pickle.load(symb_model_file_smac)
                    symb_pred_smac = symb_smac.predict(
                        X_test.T.reshape(X_test.shape[1] * X_test.shape[2], X_test.shape[0])
                    ).reshape(X_test.shape[2], X_test.shape[1]).T
                    error_test[f"SR (BO)"] += np.abs(y_test - symb_pred_smac)

                    with open(
                            f"{symb_dir_rand}/n_samples{n_samples}_sampling_seed{sampling_seed}_symb_seed{symb_seed}.pkl",
                            "rb") as symb_model_file_rand:
                        symb_rand = pickle.load(symb_model_file_rand)
                    symb_pred_rand = symb_rand.predict(
                        X_test.T.reshape(X_test.shape[1] * X_test.shape[2], X_test.shape[0])
                    ).reshape(X_test.shape[2], X_test.shape[1]).T
                    error_test[f"SR (Random)"] += np.abs(y_test - symb_pred_rand)

                for key in error_test:
                    error_test[key] = error_test[key]/n_seeds_total

                filename = f"{classifier_name}_{'_'.join(parameter_names)}_{data_set}_n_samples{n_samples}"
                if evaluate_on_surrogate:
                    filename = "_".join([filename, "surrogate"])

                plot = plot_symb2d(
                    X_train_list=[None, None],
                    X_test=X_test.copy(),
                    y_test=y_test.copy(),
                    function_name=classifier.name,
                    use_same_scale=False,
                    metric_name="Surrogate MAE",
                    predictions_test=error_test,
                    parameters=optimized_parameters,
                    plot_dir=viz_plot_dir,
                    filename=filename
                )