# -*- coding: utf-8 -*-
"""DABench pilot 的參考解：照題目與限制**獨立**寫的一組解，用來證明「照限制做會得到標準答案」。

這支在架構裡承重什麼：r534 的正控制只有 1/20（LCB 沒有參考解）；這一份讓 DABench pilot 的
每一題都有一個「正確的解會被 score.py 判過」的證據（`gauge_bank.py --reproduce`）。

寫法紀律（誠實邊界，改這支要保留）：
1. 每個函式是**看題目、限制、格式**寫的，寫的時候沒有看標準答案。第一次跑完之後**不為了對上答案改解讀**；
   只准修「程式寫錯」（欄名打錯、例外），修了要在該函式的 docstring 記一行。
2. 限制沒講清楚的地方（樣本／母體標準差、z-score 的 ddof、時區……）用 pandas／scipy 的預設，
   並在函式 docstring 記下選了哪一個。重現不了的題照實記、具名排除，不刪。
3. 「重現得了」只證明**存在一個**照限制做的解會得到標準答案；不證明沒有第二種合理解讀。

每個函式：`f(path) -> list[(name, value_text)]`，path 是工作區裡的 `data/<檔名>`。
"""
from __future__ import annotations

import statistics

import numpy as np
import pandas as pd
from scipy import stats


def _f(x: float, d: int = 2) -> str:
    return f"{x:.{d}f}"


def _lead_int(s: pd.Series) -> pd.Series:
    """'630308[495000-801000]' → 630308（'[' 之前的整數）。"""
    return pd.to_numeric(s.astype(str).str.split("[").str[0].str.strip(), errors="coerce")


def _hms_seconds(s: pd.Series) -> pd.Series:
    return pd.to_timedelta(s).dt.total_seconds()


# ── easy ────────────────────────────────────────────────────────────────

def s427(p):
    df = pd.read_csv(p)
    return [("null_entries_count", str(int(df["min_p"].isnull().sum())))]


def s57(p):
    """'No. of cases'／'No. of deaths' 取 '[' 之前的整數。"""
    df = pd.read_csv(p)
    c, d = _lead_int(df["No. of cases"]), _lead_int(df["No. of deaths"])
    return [("correlation_coefficient", _f(c.corr(d)))]


def s507(p):
    df = pd.read_csv(p)
    return [("total_hotels", str(int((df["star_rating"] == 5).sum())))]


def s218(p):
    df = pd.read_csv(p)
    return [("correlation_coefficient", _f(df["positive_diffsel"].corr(df["negative_diffsel"])))]


def s657(p):
    """std 用 pandas 預設（樣本，ddof=1）。"""
    c = pd.read_csv(p)["Close"]
    return [("mean_close", _f(c.mean())), ("median_close", _f(c.median())),
            ("std_close", _f(c.std()))]


def s517(p):
    df = pd.read_csv(p)[["Pclass", "Fare"]].dropna()
    return [("correlation_pclass_fare", _f(df["Pclass"].corr(df["Fare"])))]


def s129(p):
    """題目指定母體標準差（ddof=0）。"""
    f = pd.read_csv(p)["Fare"]
    return [("mean_fare", _f(f.mean())), ("std_dev_fare", _f(f.std(ddof=0)))]


def s55(p):
    """'[' 之前的整數；平均四捨五入成整數。"""
    c = _lead_int(pd.read_csv(p)["No. of cases"]).dropna()
    return [("mean_cases", str(int(round(c.mean()))))]


def s216(p):
    """std 用 pandas 預設（ddof=1）。"""
    a = pd.read_csv(p)["abs_diffsel"]
    return [("mean", _f(a.mean())), ("std_dev", _f(a.std()))]


def s666(p):
    """「built-in Python statistical functions」⇒ statistics.mean／statistics.stdev（樣本）。"""
    v = pd.read_csv(p)["MedianHouseValue"].dropna().tolist()
    return [("mean_value", _f(statistics.mean(v), 4)), ("std_dev", _f(statistics.stdev(v), 4))]


def s553(p):
    """IQR；四分位數用 pandas 預設（linear）。"""
    t = pd.read_csv(p)["TPH_PLT"]
    q1, q3 = t.quantile(0.25), t.quantile(0.75)
    iqr = q3 - q1
    n = int(((t < q1 - 1.5 * iqr) | (t > q3 + 1.5 * iqr)).sum())
    return [("outliers_count", str(n))]


def s32(p):
    """std 用 pandas 預設（ddof=1）。"""
    s = pd.read_csv(p)["importance.score"]
    return [("importance_score_mean", _f(s.mean())), ("importance_score_std", _f(s.std()))]


def s26(p):
    df = pd.read_csv(p)[["charges", "children"]].dropna()
    return [("correlation_coefficient", _f(df["charges"].corr(df["children"])))]


# ── medium ──────────────────────────────────────────────────────────────

def s426(p):
    """最高 max_storm_cat 的第一個風暴（資料順序）；同名多列取 max_sust_wind 的最大值。"""
    df = pd.read_csv(p)
    name = df.loc[df["max_storm_cat"].idxmax(), "name"]
    return [("max_wind_speed", _f(df.loc[df["name"] == name, "max_sust_wind"].max()))]


def s105(p):
    df = pd.read_csv(p)[["ApplicantIncome", "LoanAmount"]].dropna()
    return [("correlation_coefficient", _f(df["ApplicantIncome"].corr(df["LoanAmount"])))]


def s721(p):
    df = pd.read_csv(p)
    return [("correlation_coefficient", _f(df["mpg"].corr(df["weight"])))]


def s588(p):
    """'avg. wait time'（HH:MM:SS）轉秒；z-score 用 scipy.stats.zscore（ddof=0）。
    修正（程式錯，不是解讀）：第一次跑 KeyError——CSV 欄名尾端有空白，改成先 strip 欄名。"""
    df = pd.read_csv(p)
    df.columns = [c.strip() for c in df.columns]
    w = _hms_seconds(df["avg. wait time"])
    z = stats.zscore(w)
    return [("num_of_outliers", str(int((np.abs(z) > 3).sum())))]


def s8(p):
    """題目指定母體標準差（ddof=0）。"""
    df = pd.read_csv(p)
    out = []
    for c in (1, 2, 3):
        f = df.loc[df["Pclass"] == c, "Fare"]
        out += [(f"mean_fare_class{c}", _f(f.mean())), (f"median_fare_class{c}", _f(f.median())),
                (f"std_dev_fare_class{c}", _f(f.std(ddof=0)))]
    return out


def s35(p):
    """z-score 用 scipy.stats.zscore（ddof=0）。"""
    r = pd.read_csv(p)["row retention time"].dropna()
    z = stats.zscore(r)
    return [("removed_outliers_count", str(int((np.abs(z) > 3).sum())))]


def s176(p):
    df = pd.read_csv(p)
    m = df[(df["Sex"] == "male") & (df["Survived"] == 1) & (df["Fare"] > df["Fare"].mean())]
    return [("median_age", _f(m["Age"].dropna().median()))]


def s688(p):
    """dt 是 unix 秒；用 pd.to_datetime(unit='s')（UTC）取小時。"""
    h = pd.to_datetime(pd.read_csv(p)["dt"], unit="s").dt.hour
    return [("morning", str(int(((h >= 6) & (h < 12)).sum()))),
            ("afternoon", str(int(((h >= 12) & (h < 18)).sum()))),
            ("evening", str(int((h >= 18).sum()))),
            ("night", str(int((h < 6).sum())))]


def s514(p):
    """高：城市平均 > 2×整體平均；低：城市平均 < 整體平均／2。"""
    df = pd.read_csv(p)
    overall = df["review_count"].mean()
    city = df.groupby("city_name")["review_count"].mean()
    return [("higher_city_count", str(int((city > 2 * overall).sum()))),
            ("lower_city_count", str(int((city < overall / 2).sum())))]


def s250(p):
    """std 用 pandas 預設（ddof=1）。"""
    df = pd.read_csv(p)
    d = (df["batting_average"] - df["on_base_percentage"]).dropna()
    return [("mean", _f(d.mean())), ("std_dev", _f(d.std()))]


def s587(p):
    """修正（程式錯，不是解讀）：第一次跑 KeyError——CSV 欄名尾端有空白，改成先 strip 欄名。"""
    df = pd.read_csv(p)
    df.columns = [c.strip() for c in df.columns]
    w = _hms_seconds(df["avg. wait time"])
    return [("correlation_coefficient", _f(df["avg. num. agents talking"].corr(w), 3))]


def s5(p):
    df = pd.read_csv(p)
    fs = df["SibSp"] + df["Parch"]
    return [("correlation_coefficient", _f(fs.corr(df["Fare"])))]


def s520(p):
    df = pd.read_csv(p)
    fs = df["SibSp"] + df["Parch"]
    return [("correlation_coefficient", _f(fs.corr(df["Survived"])))]


# ── hard ────────────────────────────────────────────────────────────────

def s144(p):
    """std 用 pandas 預設（ddof=1）；Anderson-Darling 用 scipy.stats.anderson 的 5% 臨界值。"""
    df = pd.read_csv(p)
    out = [("mean_dem", _f(df["per_dem"].mean())), ("mean_gop", _f(df["per_gop"].mean())),
           ("std_dev_dem", _f(df["per_dem"].std(), 3)), ("std_dev_gop", _f(df["per_gop"].std(), 3))]
    for k in ("dem", "gop"):
        r = stats.anderson(df[f"per_{k}"].dropna())
        crit = dict(zip(r.significance_level, r.critical_values))[5.0]
        out.append((f"dist_{k}", "Not Normal" if r.statistic > crit else "Normal"))
    return out


def s725(p):
    df = pd.read_csv(p)
    top = df["displacement"].value_counts().head(3).index
    out = []
    for i, v in enumerate(top, 1):
        m = df.loc[df["displacement"] == v, "mpg"]
        out += [(f"mean{i}", _f(m.mean())), (f"median{i}", _f(m.median()))]
    return out


def s723(p):
    """題目指定母體標準差（ddof=0）。"""
    df = pd.read_csv(p)
    r = df["horsepower"] / df["weight"]
    return [("mean_ratio", _f(r.mean())), ("std_ratio", _f(r.std(ddof=0)))]


def s378(p):
    """兩個 passes 欄 to_numeric(errors='coerce') 後以平均補值；統計量用 pandas 預設
    （std ddof=1、skew、kurt＝超額峰度）。"""
    df = pd.read_csv(p)
    trips = "Trips over the past 24-hours (midnight to 11:59pm)"
    pre = df[trips].copy()
    for c in ("24-Hour Passes Purchased (midnight to 11:59 pm)",
              "7-Day Passes Purchased (midnight to 11:59 pm)"):
        v = pd.to_numeric(df[c], errors="coerce")
        df[c] = v.fillna(v.mean())
    post = df[trips]
    out = []
    for tag, s in (("pre", pre), ("post", post)):
        out += [(f"{tag}_mean", _f(s.mean())), (f"{tag}_median", _f(s.median())),
                (f"{tag}_sd", _f(s.std())), (f"{tag}_skewness", _f(s.skew())),
                (f"{tag}_kurtosis", _f(s.kurt()))]
    return out


def s521(p):
    """Age／Sex／Fare／Survived 有缺值的列先丟掉；Sex 以 male=1、female=0 編碼。"""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score
    from sklearn.model_selection import train_test_split
    df = pd.read_csv(p)[["Age", "Sex", "Fare", "Survived"]].dropna()
    X = pd.DataFrame({"Age": df["Age"], "Sex": (df["Sex"] == "male").astype(int), "Fare": df["Fare"]})
    Xtr, Xte, ytr, yte = train_test_split(X, df["Survived"], test_size=0.3, random_state=42)
    m = LogisticRegression().fit(Xtr, ytr)
    return [("classifier_accuracy", _f(accuracy_score(yte, m.predict(Xte))))]


def s732(p):
    df = pd.read_csv(p)
    before = int(df["lifeexp"].isnull().sum())
    df["lifeexp"] = df["lifeexp"].fillna(df.groupby("country")["lifeexp"].transform("mean"))
    df["lifeexp"] = df["lifeexp"].fillna(df["lifeexp"].mean())
    return [("number_of_missing_values_in_lifeexp_before", str(before)),
            ("number_of_missing_values_in_lifeexp_after", str(int(df["lifeexp"].isnull().sum())))]


def s39(p):
    """Shapiro-Wilk（scipy）；p<0.05 ⇒ 自然對數；std 用 pandas 預設（ddof=1）。"""
    s = pd.read_csv(p)["importance.score"].dropna()
    pv = stats.shapiro(s).pvalue
    t = np.log(s) if pv < 0.05 else s
    return [("is_normal", _f(pv, 4)), ("transformed_importance_score_mean", _f(t.mean())),
            ("transformed_importance_score_std", _f(t.std()))]


def s665(p):
    """數值欄以各欄平均補值；High ≥ p75、Low ≤ p25、其餘為 Medium；四分位數用 pandas 預設。"""
    df = pd.read_csv(p)
    num = df.select_dtypes("number").columns
    df[num] = df[num].fillna(df[num].mean())
    c = df["Close"]
    q1, q3 = c.quantile(0.25), c.quantile(0.75)
    hi, lo = c >= q3, c <= q1
    mid = ~(hi | lo)
    n = len(c)
    return [("high_count", str(int(hi.sum()))), ("high_proportion", _f(hi.sum() / n)),
            ("medium_count", str(int(mid.sum()))), ("medium_proportion", _f(mid.sum() / n)),
            ("low_count", str(int(lo.sum()))), ("low_proportion", _f(lo.sum() / n))]


def s249(p):
    df = pd.read_csv(p)[["number_of_doubles", "salary_in_thousands_of_dollars"]].dropna()
    r, pv = stats.pearsonr(df["number_of_doubles"], df["salary_in_thousands_of_dollars"])
    return [("correlation_coefficient", _f(r)), ("p_value", _f(pv, 4))]


def s619(p):
    """「trajectory duration」取 poiDuration 欄；z-score 用 scipy（ddof=0）；np.mean／np.std（ddof=0）。"""
    d = pd.read_csv(p)["poiDuration"]
    z = stats.zscore(d)
    k = d[np.abs(z) <= 2.5].to_numpy()
    return [("mean_new", _f(np.mean(k))), ("std_dev_new", _f(np.std(k)))]


def s724(p):
    """z-score 用 scipy（ddof=0）；題目指定母體標準差。"""
    a = pd.read_csv(p)["acceleration"]
    k = a[np.abs(stats.zscore(a)) <= 3]
    return [("mean_acceleration", _f(k.mean())), ("std_acceleration", _f(k.std(ddof=0)))]


def s669(p):
    """IQR（pandas 預設四分位數）；std 用 pandas 預設（ddof=1）。"""
    m = pd.read_csv(p)["MedInc"]
    q1, q3 = m.quantile(0.25), m.quantile(0.75)
    iqr = q3 - q1
    k = m[(m >= q1 - 1.5 * iqr) & (m <= q3 + 1.5 * iqr)]
    return [("mean", _f(k.mean())), ("standard_deviation", _f(k.std()))]


def s453(p):
    """欄名前面有空白（' WINDSPEED'、' AT'）；風速 |z|>3（z 以 pandas mean／std ddof=1）換成平均；
    AT 缺值補平均。"""
    df = pd.read_csv(p)
    df.columns = [c.strip() for c in df.columns]
    w, at = df["WINDSPEED"], df["AT"]
    out = [("mean_wind_pre", _f(w.mean())), ("mean_atmos_temp_pre", _f(at.mean()))]
    mu, sd = w.mean(), w.std()
    w2 = w.where(((w - mu) / sd).abs() <= 3, mu)
    at2 = at.fillna(at.mean())
    out += [("mean_wind_post", _f(w2.mean())), ("mean_atmos_temp_post", _f(at2.mean()))]
    return out


SOLUTIONS = {int(k[1:]): v for k, v in dict(globals()).items()
             if k[:1] == "s" and k[1:].isdigit() and callable(v)}
