if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter
import os
import pickle
import click
import mlflow

from mlflow.entities import ViewType
from mlflow.tracking import MlflowClient

from mlflow import sklearn
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction import DictVectorizer

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
import xgboost as xgb
from xgboost import XGBClassifier

from sklearn.metrics import f1_score, roc_auc_score
from sklearn.preprocessing import LabelBinarizer
from hyperopt import STATUS_OK, Trials, fmin, hp, tpe
from hyperopt.pyll import scope

HPO_EXPERIMENT_NAME = "heart-disease-experiment"
EXPERIMENT_NAME = "random-forest-best-models"
RF_PARAMS = ['max_depth', 'n_estimators',
            'min_samples_split', 'min_samples_leaf',
            'random_state']
VALID_RF_PARAMS = ['max_depth', 'n_estimators', 'min_samples_split', 'min_samples_leaf', 'random_state']




mlflow.set_tracking_uri("http://mlflow:5000")
mlflow.set_experiment(EXPERIMENT_NAME)
# mlflow.sklearn.autolog(silent=True)



def train_and_log_model(params, X_train, y_train, X_test, y_test):
    with mlflow.start_run():
        # Filter out any parameters that are not valid for the RandomForestClassifier
        params = {param: int(params[param]) for param in RF_PARAMS if param in params and param in VALID_RF_PARAMS}

        rf = RandomForestClassifier(**params)
        rf.fit(X_train, y_train)
        y_pred = rf.predict(X_test)
        # Evaluate model on the validation and test sets
        f1 = f1_score(y_test, y_pred)
        roc_auc = roc_auc_score(y_test, y_pred)
        mlflow.log_metric("f1_score", f1)
        mlflow.log_metric("roc_auc_score", roc_auc)
        for param in VALID_RF_PARAMS:
            param_value = params.get(param, None)
            if param_value is not None:
                mlflow.log_param(param, param_value)
@data_exporter
def export_data(df, *args, **kwargs):
    """
    Exports data to some source.

    Args:
        data: The output from the upstream parent block
        args: The output from any additional upstream blocks (if applicable)

    Output (optional):
        Optionally return any object and it'll be logged and
        displayed when inspecting the block run.
    """
    # Specify your data exporting logic here
    X_train = df[0]
    X_test = df[1]
    y_train = df[2]
    y_test = df[3]
    top_n = 5 #top 5
    
    
    client = MlflowClient()
    experiment = client.get_experiment_by_name(HPO_EXPERIMENT_NAME)
    print(experiment)
    runs = client.search_runs(
        experiment_ids=experiment.experiment_id,
        run_view_type=ViewType.ACTIVE_ONLY,
        max_results=top_n,
        order_by=["metrics.f1_score DESC", "metrics.roc_auc_score DESC", "attributes.end_time ASC"]
    )
    for run in runs:
        train_and_log_model(params = run.data.params, X_train=X_train, y_train=y_train, X_test=X_test, y_test=y_test)
    
    experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
    best_run = client.search_runs(experiment_ids=experiment.experiment_id,
                                run_view_type=ViewType.ACTIVE_ONLY,
                                max_results=1,
                                order_by=["metrics.f1_score DESC", "metrics.roc_auc_score DESC", "attributes.end_time ASC"])[0]
    print(f"Best model ID: {best_run.info.run_id}")
    print("Best test F1 Score: ", round(best_run.data.metrics['f1_score'],3))
    print("Best test ROC AUC Score: ", round(best_run.data.metrics['roc_auc_score'],3))
    # print("Best test duration time: ", best_run.info.duration , "ms")
    mlflow.register_model(f"runs:/{best_run.info.run_id}/model", 'best_run_model')
    

    