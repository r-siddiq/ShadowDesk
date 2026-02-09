import logging
import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

sys.path.insert(0, "/opt/airflow/project")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2026, 2, 17),
    "email_on_failure": True,
    "email": ["admin@example.com"],
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

WATCHLIST = [
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "NFLX",
    "AMD",
    "INTC",
    "BA",
    "JPM",
    "V",
    "MA",
    "PYPL",
    "DIS",
    "KO",
    "PEP",
    "WMT",
    "COST",
    "NKE",
    "SBUX",
    "CRM",
    "ADBE",
    "ORCL",
]

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MLFLOW_URI = os.getenv("MLFLOW_URI", "http://localhost:30368")


def update_hourly_data(**context):
    try:
        from cluster_b.train.hourly_data_ingestion import HourlyStockDataIngestion

        ingestion = HourlyStockDataIngestion(
            minio_endpoint=MINIO_ENDPOINT,
            access_key=os.getenv("MINIO_ACCESS_KEY", ""),
            secret_key=os.getenv("MINIO_SECRET_KEY", ""),
            bucket_name="stock-data",
        )

        result = ingestion.update_all_symbols(WATCHLIST, period="1mo")

        logger.info(f"Update hourly data result: {result}")

        return {
            "status": "success",
            "total_symbols": result.get("total_symbols", 0),
            "success_count": result.get("success_count", 0),
            "error_count": result.get("error_count", 0),
        }
    except Exception as e:
        logger.error(f"Error updating hourly data: {e}")
        return {"status": "error", "message": str(e)}


def check_stop_losses(**context):
    try:
        from cluster_b.trading.broker import AlpacaBroker
        from cluster_b.trading.executor import TradingExecutor

        broker = AlpacaBroker(paper=True)
        executor = TradingExecutor(
            broker=broker,
            max_positions=10,
            max_position_pct=0.02,
            stop_loss_pct=0.15,
            max_total_risk=0.25,
            min_confidence=0.6,
        )

        stop_loss_positions = executor.check_all_stop_losses()

        executed_sells = []
        for sl_pos in stop_loss_positions:
            try:
                result = executor.execute_sell(sl_pos["symbol"], reason="stop_loss")
                executed_sells.append(result)
                logger.info(f"Executed stop loss for {sl_pos['symbol']}: {result}")
            except Exception as e:
                logger.error(f"Failed to execute stop loss for {sl_pos['symbol']}: {e}")

        return {
            "status": "success",
            "positions_checked": len(executor.get_open_positions()),
            "stop_losses_triggered": len(stop_loss_positions),
            "executed_sells": executed_sells,
        }
    except Exception as e:
        logger.error(f"Error checking stop losses: {e}")
        return {"status": "error", "message": str(e)}


def generate_signals(**context):
    try:
        from cluster_b.trading.signals import TradingSignals

        signals = TradingSignals(
            minio_endpoint=MINIO_ENDPOINT,
            access_key=os.getenv("MINIO_ACCESS_KEY", ""),
            secret_key=os.getenv("MINIO_SECRET_KEY", ""),
            bucket_name="stock-data",
        )

        signals.load_model()

        results = signals.get_signals(WATCHLIST, min_confidence=0.6)

        logger.info(f"Generated {len(results)} signals from {len(WATCHLIST)} symbols")

        buy_signals = [s for s in results if s.get("signal") == "BUY"]
        sell_signals = [s for s in results if s.get("signal") == "SELL"]

        return {
            "status": "success",
            "total_signals": len(results),
            "buy_signals": len(buy_signals),
            "sell_signals": len(sell_signals),
            "signals": results,
        }
    except Exception as e:
        logger.error(f"Error generating signals: {e}")
        return {"status": "error", "message": str(e)}


def execute_trades(**context):
    try:
        from cluster_b.trading.broker import AlpacaBroker
        from cluster_b.trading.executor import TradingExecutor
        from cluster_b.trading.signals import TradingSignals

        broker = AlpacaBroker(paper=True)
        signals = TradingSignals(
            minio_endpoint=MINIO_ENDPOINT,
            access_key=os.getenv("MINIO_ACCESS_KEY", ""),
            secret_key=os.getenv("MINIO_SECRET_KEY", ""),
            bucket_name="stock-data",
        )

        executor = TradingExecutor(
            broker=broker,
            signals=signals,
            max_positions=10,
            max_position_pct=0.02,
            stop_loss_pct=0.15,
            max_total_risk=0.25,
            min_confidence=0.6,
        )

        cycle_results = executor.run_cycle(WATCHLIST)

        logger.info(f"Trading cycle results: {cycle_results}")

        return {
            "status": "success",
            "positions_before": cycle_results.get("positions_before", 0),
            "positions_after": cycle_results.get("positions_after", 0),
            "stop_losses_triggered": len(cycle_results.get("stop_losses_triggered", [])),
            "signals_generated": len(cycle_results.get("signals_generated", [])),
            "executions": len(cycle_results.get("executions", [])),
            "errors": cycle_results.get("errors", []),
        }
    except Exception as e:
        logger.error(f"Error executing trades: {e}")
        return {"status": "error", "message": str(e)}


def log_performance(**context):
    try:
        from cluster_b.trading.broker import AlpacaBroker
        from cluster_b.trading.executor import TradingExecutor

        broker = AlpacaBroker(paper=True)
        executor = TradingExecutor(broker=broker)

        stats = executor.get_performance_stats()

        logger.info(f"Performance stats: {stats}")

        account = broker.get_account()

        return {
            "status": "success",
            "portfolio_value": account.get("portfolio_value"),
            "cash": account.get("cash"),
            "equity": account.get("equity"),
            "buying_power": account.get("buying_power"),
            "open_positions": stats.get("open_positions", 0),
            "total_orders": stats.get("total_orders", 0),
            "win_rate": stats.get("win_rate", 0),
            "total_pnl": stats.get("total_pnl", 0),
        }
    except Exception as e:
        logger.error(f"Error logging performance: {e}")
        return {"status": "error", "message": str(e)}


with DAG(
    "autonomous_trading",
    default_args=default_args,
    description="Autonomous trading with ML signals",
    schedule="0 * * * *",
    catchup=False,
) as dag:
    update_task = PythonOperator(
        task_id="update_hourly_data",
        python_callable=update_hourly_data,
    )

    check_sl_task = PythonOperator(
        task_id="check_stop_losses",
        python_callable=check_stop_losses,
    )

    generate_signals_task = PythonOperator(
        task_id="generate_signals",
        python_callable=generate_signals,
    )

    execute_trades_task = PythonOperator(
        task_id="execute_trades",
        python_callable=execute_trades,
    )

    log_perf_task = PythonOperator(
        task_id="log_performance",
        python_callable=log_performance,
    )

    (update_task >> check_sl_task >> generate_signals_task >> execute_trades_task >> log_perf_task)


daily_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2026, 2, 17),
    "email_on_failure": True,
    "email": ["admin@example.com"],
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}


def retrain_model(**context):
    try:
        from cluster_b.train.xgboost_trainer import XGBoostStockTrainer

        trainer = XGBoostStockTrainer(
            minio_endpoint=MINIO_ENDPOINT,
            mlflow_uri=MLFLOW_URI,
            access_key=os.getenv("MINIO_ACCESS_KEY", ""),
            secret_key=os.getenv("MINIO_SECRET_KEY", ""),
            bucket_name="stock-data",
        )

        result = trainer.train()

        logger.info(f"Model retrain result: {result}")

        return {
            "status": "success",
            "model_version": result.get("model_version", "unknown"),
            "metrics": result.get("metrics", {}),
        }
    except Exception as e:
        logger.error(f"Error retraining model: {e}")
        return {"status": "error", "message": str(e)}


with DAG(
    "autonomous_trading_daily_retrain",
    default_args=daily_args,
    description="Daily model retraining for autonomous trading",
    schedule="0 1 * * *",
    catchup=False,
) as retrain_dag:
    retrain_task = PythonOperator(
        task_id="retrain_model",
        python_callable=retrain_model,
    )

    log_perf_task_daily = PythonOperator(
        task_id="log_performance",
        python_callable=log_performance,
    )

    retrain_task >> log_perf_task_daily
