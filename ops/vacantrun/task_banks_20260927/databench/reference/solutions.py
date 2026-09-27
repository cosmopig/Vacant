# -*- coding: utf-8 -*-
"""DataBench pilot 的參考解：照題目**獨立**寫的一組 pandas 解，證明「照題意算會得到官方答案」。

這支在架構裡承重什麼：官方答案本身就是正確答案（對它計分只是恆真式）；這一份多證明一件事——
**存在一個照題意寫的程式**會被 `score.py` 判對，所以「0 分」不是量具量不動。

寫法紀律（誠實邊界，改這支要保留）：
1. 每個函式看題目寫，寫的時候沒有看官方答案。第一次跑完後**不為了對上答案改解讀**；只准修程式錯
   （欄名、型別轉換），修了在函式 docstring 記一行。
2. 題意有歧義的地方（「最好」是高還是低、「最高層」是哪一層……）在 docstring 記下選了哪一個；
   重現不了的題照實記、具名排除。
3. 「重現得了」只證明**存在一個**合理解讀會得到官方答案，不證明沒有第二種合理解讀。

鍵＝「資料集#qa 列號」；每個函式 `f(df) -> str`（agent 寫進 answer.txt 的那一行）。
`df` 是工作區裡那份 CSV 用 `pandas.read_csv` 讀回來的表（RULE_TEXT R6），不是 parquet 原檔。
079_Coffee、070_OpenFoodFacts 的解在改成 CSV（兩者超過 2 MB 不再合格）之後刪掉了。
"""
from __future__ import annotations

import pandas as pd

KG_PER_LB = 0.45359237


def _py(x):
    return x.item() if hasattr(x, "item") else x


def _list(xs) -> str:
    return repr([_py(x) for x in xs])


S = {}


def sol(key):
    def deco(f):
        S[key] = f
        return f
    return deco


# ── boolean ─────────────────────────────────────────────────────────────
@sol("074_Lift#3")
def _(df):
    """330 磅換成公斤比。"""
    return str(bool(df["Amount Lifted (kg)"].min() < 330 * KG_PER_LB))


@sol("066_IBM_HR#8")
def _(df):
    return str(bool(df["StandardHours"].nunique() == 1))


@sol("069_Taxonomy#7")
def _(df):
    """「valid unique value」解讀成 Unique ID 沒有缺值而且兩兩不同。"""
    u = df["Unique ID"]
    return str(bool(u.notna().all() and u.is_unique))


@sol("080_Books#4")
def _(df):
    """「enough stock」解讀成每一本的 Stock Status 都是 In Stock。"""
    return str(bool((df["Stock Status"] == "In Stock").all()))


@sol("074_Lift#6")
def _(df):
    """103000 g＝103 kg ⇒ 落在 105 kg 量級（93–105）。"""
    return str(bool(df.loc[df["Weight Class"] == "105 kg", "Age"].mean() > 40))


@sol("073_Med_Cost#6")
def _(df):
    return str(bool((df["region"] == "northeast").any()))


@sol("066_IBM_HR#6")
def _(df):
    return str(bool((df["BusinessTravel"] == "Travel_Frequently").sum()
                    > (df["Department"] == "Human Resources").sum()))


@sol("069_Taxonomy#6")
def _(df):
    return str(bool(len(df) == 703))


# ── category ────────────────────────────────────────────────────────────
@sol("066_IBM_HR#14")
def _(df):
    return str(df.groupby("Gender", observed=True)["JobSatisfaction"].mean().idxmax())


@sol("066_IBM_HR#12")
def _(df):
    return str(df["EducationField"].value_counts().idxmax())


@sol("076_NBA#14")
def _(df):
    """單一列（球員-球季）的 STL 最大者。"""
    return str(df.loc[df["STL"].idxmax(), "PLAYER"])


@sol("073_Med_Cost#17")
def _(df):
    return str(df.loc[df["bmi"].idxmin(), "smoker"])


@sol("069_Taxonomy#8")
def _(df):
    """每個 Tier 1 名稱底下的列數（含間接）最多者。"""
    return str(df["Tier 1"].value_counts().idxmax())


@sol("078_Fires#13")
def _(df):
    """星期名稱（calendar_names_2）的平均風速最大者。"""
    return str(df.groupby("calendar_names_2")["wind"].mean().idxmax())


@sol("074_Lift#9")
def _(df):
    return str(df.groupby("Weight Class", observed=True)["Amount Lifted (kg)"].mean().idxmax())


@sol("075_Mortality#11")
def _(df):
    """「best」解讀成死亡率（Rate）平均最低。"""
    return str(df.groupby("Status", observed=True)["Rate"].mean().idxmin())


# ── number ──────────────────────────────────────────────────────────────
@sol("075_Mortality#13")
def _(df):
    """「ratio column」解讀成 Rate 欄。"""
    return str(_py(df["Rate"].max()))


@sol("080_Books#23")
def _(df):
    return str(int(df["Category"].astype(str).str.contains("Islamic", case=False).sum()))


@sol("071_COL#17")
def _(df):
    return str(int(df["Country"].nunique()))


@sol("076_NBA#21")
def _(df):
    """2010-11 球季出現過的不同球員數（例行賽＋季後賽合併去重）。"""
    return str(int(df.loc[df["year"] == "2010-11", "PLAYER_ID"].nunique()))


@sol("077_Gestational#11")
def _(df):
    return str(_py(df.nlargest(2, "Weight")["Height"].max()))


@sol("075_Mortality#15")
def _(df):
    """「worse than 200」解讀成 Rate > 200。"""
    return str(int((df["Rate"] > 200).sum()))


@sol("066_IBM_HR#24")
def _(df):
    y = df["YearsSinceLastPromotion"]
    return str(int(y.max()) - int(y.min()))


@sol("073_Med_Cost#18")
def _(df):
    return str(_py(df["bmi"].max()))


# ── list[category] ──────────────────────────────────────────────────────
@sol("078_Fires#32")
def _(df):
    order = ["January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]
    present = set(df["calendar_names_1"].dropna())
    return _list([m for m in order if m in present])


@sol("066_IBM_HR#31")
def _(df):
    return _list([str(x) for x in df["JobRole"].value_counts().head(3).index])


@sol("076_NBA#32")
def _(df):
    return _list([str(x) for x in df.groupby("TEAM", observed=True)["REB"].sum().nlargest(5).index])


@sol("073_Med_Cost#30")
def _(df):
    return _list([str(x) for x in df.loc[df["age"] > 60, "smoker"].unique()])


@sol("076_NBA#33")
def _(df):
    return _list([str(x) for x in df.groupby("PLAYER", observed=True)["STL"].sum().nlargest(2).index])


@sol("080_Books#35")
def _(df):
    """「not on sale」解讀成 Discount Offer == 'No'。"""
    return _list([str(x) for x in df.loc[df["Discount Offer"] == "No", "Author"]])


@sol("071_COL#34")
def _(df):
    return _list([str(x) for x in df.nlargest(5, "Local Purchasing Power Index")["Country"]])


@sol("069_Taxonomy#28")
def _(df):
    """「highest tier」解讀成最上層（Tier 1），依出現順序取前 3 個不同值。"""
    return _list([str(x) for x in pd.unique(df["Tier 1"].dropna())[:3]])


# ── list[number] ────────────────────────────────────────────────────────
@sol("078_Fires#26")
def _(df):
    return _list(df["DC"].nsmallest(5).tolist())


@sol("076_NBA#26")
def _(df):
    return _list(df["PTS"].nlargest(4).tolist())


@sol("071_COL#26")
def _(df):
    """「associated index values」解讀成那三國的 Groceries Index。"""
    return _list(df.nlargest(3, "Groceries Index")["Groceries Index"].tolist())


@sol("066_IBM_HR#37")
def _(df):
    return _list(df["JobLevel"].value_counts().head(4).index.tolist())


@sol("080_Books#27")
def _(df):
    return _list(df["Book Length (Pages)"].head(5).tolist())


@sol("077_Gestational#22")
def _(df):
    return _list(df["Height"].nlargest(3).tolist())


@sol("075_Mortality#22")
def _(df):
    """「error deviations」解讀成 SE 欄。"""
    return _list(df["SE"].nsmallest(5).tolist())


@sol("072_Admissions#35")
def _(df):
    return _list(df.nsmallest(5, "CGPA")["University Rating"].tolist())


# ── 第二批（改成 CSV、候選順序重排之後補寫；紀律同上：寫的時候沒看官方答案） ────────

# boolean
@sol("071_COL#2")
def _(df):
    return str(bool((df["Rent Index"] > 65).any()))


@sol("076_NBA#0")
def _(df):
    return str(bool((df["PTS"] == 1000).any()))


@sol("066_IBM_HR#4")
def _(df):
    d = df["Department"]
    return str(bool((d == "Research & Development").sum() > (d == "Sales").sum()))


@sol("076_NBA#6")
def _(df):
    """「every game of a season」解讀成例行賽 GP == 82（完整球季的場數）。"""
    return str(bool(((df["GP"] == 82) & (df["Season_type"].str.startswith("Regular"))).any()))


@sol("072_Admissions#2")
def _(df):
    return str(bool(df["CGPA"].max() > 9.5))


@sol("077_Gestational#1")
def _(df):
    return str(bool((df["Age"] < 18).any()))


@sol("077_Gestational#8")
def _(df):
    """50000 g＝50 kg；Weight 欄是公斤。"""
    return str(bool((df["Weight"] == 50).any()))


@sol("077_Gestational#2")
def _(df):
    return str(bool((df["Pregnancy No"] == 0).any()))


# category
@sol("071_COL#12")
def _(df):
    """「world rent」解讀成 Rent Index。"""
    return str(df.nlargest(2, "Rent Index")["Country"].iloc[1])


@sol("066_IBM_HR#10")
def _(df):
    return str(df.groupby("Department")["YearsAtCompany"].mean().idxmax())


@sol("074_Lift#11")
def _(df):
    return str(df.groupby("Lift Type")["Amount Lifted (kg)"].mean().idxmax())


@sol("073_Med_Cost#10")
def _(df):
    return str(df["sex"].value_counts().idxmax())


@sol("078_Fires#11")
def _(df):
    """「driest day」解讀成相對濕度 RH 最低的那一列。"""
    return str(df.loc[df["RH"].idxmin(), "calendar_names_1"])


@sol("071_COL#14")
def _(df):
    return str(df.loc[(df["Groceries Index"] - 80).abs().idxmin(), "Country"])


@sol("066_IBM_HR#16")
def _(df):
    return str(df["EducationField"].value_counts().idxmin())


@sol("069_Taxonomy#13")
def _(df):
    """「third level」＝Tier 3。"""
    return str(df["Tier 3"].dropna().iloc[0])


# number
@sol("072_Admissions#26")
def _(df):
    return str(int((df["SOP"] == 5).sum()))


@sol("071_COL#15")
def _(df):
    """「most expensive country to live in」＝Cost of Living Index 最高。"""
    return str(_py(df["Cost of Living Index"].max()))


@sol("071_COL#19")
def _(df):
    r = df["Restaurant Price Index"]
    return str(round(_py(r.max() - r.min()), 6))


@sol("077_Gestational#18")
def _(df):
    return str(_py(df["Age"].median()))


@sol("074_Lift#13")
def _(df):
    return str(int(df["Lifter Name"].nunique()))


@sol("078_Fires#17")
def _(df):
    return str(_py(df["temp"].max()))


@sol("076_NBA#22")
def _(df):
    """一列＝一個球員的一個球季（含季後賽列）；數 PTS == 2000 的列。"""
    return str(int((df["PTS"] == 2000).sum()))


@sol("066_IBM_HR#18")
def _(df):
    return str(int(df["JobRole"].nunique()))


@sol("077_Gestational#7")
def _(df):
    """teen＝Age ≤ 19。"""
    return str(int((df["Age"] <= 19).sum()))


# list[category]
@sol("066_IBM_HR#34")
def _(df):
    return _list([str(x) for x in df["EducationField"].unique()])


@sol("069_Taxonomy#29")
def _(df):
    return _list([str(x) for x in pd.unique(df["Tier 1"].dropna())[:2]])


@sol("075_Mortality#28")
def _(df):
    return _list([str(x) for x in df["Status"].unique()])


@sol("073_Med_Cost#31")
def _(df):
    return _list([str(x) for x in df.nlargest(3, "bmi")["region"]])


@sol("076_NBA#29")
def _(df):
    """逐列（球員-球季）取 GP 最小的 5 列（同分取資料順序在前）。"""
    return _list([str(x) for x in df.nsmallest(5, "GP")["PLAYER"]])


@sol("076_NBA#31")
def _(df):
    return _list([str(x) for x in df.groupby("TEAM")["PTS"].sum().nlargest(5).index])


@sol("078_Fires#36")
def _(df):
    """「driest 4 percentages of RH」＝RH 最低的 4 列。"""
    return _list([str(x) for x in df.nsmallest(4, "RH")["calendar_names_1"].unique()])


@sol("080_Books#36")
def _(df):
    return _list([str(x) for x in df.loc[df["Book Length (Pages)"] < 200, "Book Title"]])


@sol("080_Books#37")
def _(df):
    """逐本列出（不去重）。"""
    return _list([str(x) for x in df.loc[df["Ratings"] > 20, "Category"]])


@sol("069_Taxonomy#30")
def _(df):
    """「second highest level」＝Tier 2。"""
    return _list([str(x) for x in pd.unique(df["Tier 2"].dropna())[:4]])


# list[number]
@sol("072_Admissions#30")
def _(df):
    """「endorsement letters」＝LOR。"""
    return _list(df["LOR"].nlargest(5).tolist())


@sol("074_Lift#27")
def _(df):
    return _list(df.loc[df["Weight Class"] == "105 kg", "Amount Lifted (kg)"].nsmallest(2).tolist())


@sol("072_Admissions#33")
def _(df):
    """「second worst possible rating」＝University Rating == 2（1–5 分）。"""
    return _list(df.loc[df["University Rating"] == 2, "CGPA"].nsmallest(2).tolist())


@sol("072_Admissions#38")
def _(df):
    return _list(df.nsmallest(5, "CGPA")["LOR"].tolist())


@sol("078_Fires#28")
def _(df):
    return _list(df["RH"].nsmallest(4).tolist())


@sol("074_Lift#26")
def _(df):
    """每個量級的 Age 全距（max − min），取最大的 3 個。"""
    g = df.groupby("Weight Class")["Age"]
    return _list((g.max() - g.min()).nlargest(3).tolist())


@sol("077_Gestational#27")
def _(df):
    return _list(sorted(df["Prediction"].unique().tolist()))


SOLUTIONS = S
