"""
Feature Engineering Module
Creates technical indicators and features for stock prediction
"""

from typing import List

import numpy as np
import pandas as pd


class FeatureEngineer:
    """Generate technical indicators and features"""

    def __init__(self):
        pass

    def add_sma(self, df: pd.DataFrame, windows: List[int] = [5, 10, 20, 50]) -> pd.DataFrame:
        """Add Simple Moving Averages"""
        df = df.copy()
        for window in windows:
            df[f"SMA_{window}"] = df["Close"].rolling(window=window).mean()
        return df

    def add_ema(self, df: pd.DataFrame, spans: List[int] = [12, 26]) -> pd.DataFrame:
        """Add Exponential Moving Averages"""
        df = df.copy()
        for span in spans:
            df[f"EMA_{span}"] = df["Close"].ewm(span=span, adjust=False).mean()
        return df

    def add_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Add Relative Strength Index"""
        df = df.copy()
        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))
        return df

    def add_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add MACD (Moving Average Convergence Divergence)"""
        df = df.copy()

        exp1 = df["Close"].ewm(span=12, adjust=False).mean()
        exp2 = df["Close"].ewm(span=26, adjust=False).mean()

        df["MACD"] = exp1 - exp2
        df["Signal_Line"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Histogram"] = df["MACD"] - df["Signal_Line"]

        return df

    def add_bollinger_bands(self, df: pd.DataFrame, window: int = 20, num_std: float = 2) -> pd.DataFrame:
        """Add Bollinger Bands"""
        df = df.copy()

        df["BB_Middle"] = df["Close"].rolling(window=window).mean()
        df["BB_Std"] = df["Close"].rolling(window=window).std()
        df["BB_Upper"] = df["BB_Middle"] + (df["BB_Std"] * num_std)
        df["BB_Lower"] = df["BB_Middle"] - (df["BB_Std"] * num_std)
        df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Middle"]
        df["BB_Position"] = (df["Close"] - df["BB_Lower"]) / (df["BB_Upper"] - df["BB_Lower"])

        return df

    def add_volatility(self, df: pd.DataFrame, windows: List[int] = [5, 10, 20]) -> pd.DataFrame:
        """Add volatility measures"""
        df = df.copy()

        # Daily returns
        df["Returns"] = df["Close"].pct_change()

        for window in windows:
            df[f"Volatility_{window}"] = df["Returns"].rolling(window=window).std() * np.sqrt(252)

        return df

    def add_price_changes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add price change features"""
        df = df.copy()

        # Daily changes
        df["Price_Change"] = df["Close"].diff()
        df["Price_Change_Pct"] = df["Close"].pct_change()

        # High-Low range
        df["HL_Range"] = df["High"] - df["Low"]
        df["HL_Range_Pct"] = df["HL_Range"] / df["Close"]

        # Volume change
        df["Volume_Change"] = df["Volume"].pct_change()

        return df

    def add_lag_features(self, df: pd.DataFrame, lags: List[int] = [1, 2, 3, 5, 10]) -> pd.DataFrame:
        """Add lagged price features"""
        df = df.copy()

        for lag in lags:
            df[f"Close_Lag_{lag}"] = df["Close"].shift(lag)
            df[f"Returns_Lag_{lag}"] = df["Returns"].shift(lag)

        return df

    def add_target(self, df: pd.DataFrame, horizon: int = 1) -> pd.DataFrame:
        """Add target variable: future return"""
        df = df.copy()

        # Future return (what we want to predict)
        df["Future_Return"] = df["Close"].shift(-horizon) / df["Close"] - 1

        # Binary target: 1 = buy (positive return), 0 = sell/hold
        df["Target"] = (df["Future_Return"] > 0).astype(int)

        return df

    def create_features(self, df: pd.DataFrame, add_target: bool = True) -> pd.DataFrame:
        """Create all features"""
        df = df.copy()

        # Add all features
        df = self.add_sma(df)
        df = self.add_ema(df)
        df = self.add_rsi(df)
        df = self.add_macd(df)
        df = self.add_bollinger_bands(df)
        df = self.add_volatility(df)
        df = self.add_price_changes(df)
        df = self.add_lag_features(df)

        if add_target:
            df = self.add_target(df)

        # Drop NaN rows (from rolling calculations)
        df = df.dropna()

        return df

    def get_feature_columns(self) -> List[str]:
        """Get list of feature column names"""
        return [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
            "SMA_5",
            "SMA_10",
            "SMA_20",
            "SMA_50",
            "EMA_12",
            "EMA_26",
            "RSI",
            "MACD",
            "Signal_Line",
            "MACD_Histogram",
            "BB_Upper",
            "BB_Lower",
            "BB_Width",
            "BB_Position",
            "Volatility_5",
            "Volatility_10",
            "Volatility_20",
            "Price_Change",
            "Price_Change_Pct",
            "HL_Range",
            "HL_Range_Pct",
            "Volume_Change",
            "Close_Lag_1",
            "Close_Lag_2",
            "Close_Lag_3",
            "Close_Lag_5",
            "Close_Lag_10",
            "Returns_Lag_1",
            "Returns_Lag_2",
            "Returns_Lag_3",
            "Returns_Lag_5",
            "Returns_Lag_10",
        ]


def main():
    """Test feature engineering"""
    # Example usage
    engineer = FeatureEngineer()
    features = engineer.get_feature_columns()
    print("Feature columns:")
    for f in features:
        print(f"  - {f}")


if __name__ == "__main__":
    main()
