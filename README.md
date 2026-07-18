# 淘宝用户行为A/B测试

## 项目背景
验证“加购后推荐相似商品”新页面设计对购买转化率的影响，对比原有浏览排序与新排序策略的业务效果。

## 项目分析
选取购买转化率、加购转化率、点击次数、购买次数、日均点击、活跃天数为核心指标，按user_id奇偶性哈希随机分流，构建用户行为-分组-指标-结果四层指标体系。

## 数据处理
- MySQL清洗92.6万条用户行为数据
- Python实现用户拆分与指标计算

## 假设验证
对两组6项指标开展显著性检验，流程包括：
- 正态性检验（Shapiro-Wilk / Kolmogorov-Smirnov）
- 方差齐性检验（Levene检验）
- 独立样本t检验 / 卡方检验
- Cohen's d效应量
- 95%置信区间

采用 **Bonferroni校正** 控制多重比较错误（α=0.05/6=0.0083），并辅以 **Bootstrap验证** 增强结论稳健性。

**结论**：在α=0.05水平下，所有指标差异均不显著，无法证明新排序策略优于原有策略。

## 项目成果
- 搭建MySQL+Python完整AB测试分析流程
- 验证新策略无显著增益
- 输出5张可视化图表，结果持久化至MySQL

| 图表 | 说明 |
|------|------|
| fig1_conversion_kde.png | 转化率KDE密度分布 |
| fig2_behavior_violin.png | 用户行为次数小提琴图 |
| fig3_results_table.png | t检验结果汇总表 |
| fig4_mean_diff_ci.png | 均值差异及95%置信区间 |
| fig5_chi_square_table.png | 卡方检验结果汇总表 |

## 技术栈
- **数据库**: MySQL
- **分析语言**: Python (pandas, numpy, scipy, matplotlib, seaborn)
- **统计方法**: 独立样本t检验、卡方检验、Bonferroni校正、Bootstrap验证
- **环境管理**: python-dotenv

## 项目结构
taobao-abtest/
├── .env # 环境变量（MySQL密码）
├── .gitignore
├── README.md
├── requirements.txt
├── data/ # 原始数据（gitignored）
│ └── UserBehavior.csv
├── sql/
│ ├── 01_create_database.sql
│ └── 02_data_processing.sql
├── src/
│ ├── ab_test_analysis.py # 主分析脚本
│ └── data_import.py # 数据导入脚本
└── output/ # 可视化输出
├── fig1_conversion_kde.png
├── fig2_behavior_violin.png
├── fig3_results_table.png
├── fig4_mean_diff_ci.png
└── fig5_chi_square_table.png

text

## 快速开始
1. 克隆仓库
2. 创建虚拟环境：`python -m venv .venv`
3. 激活虚拟环境并安装依赖：`pip install -r requirements.txt`
4. 配置 `.env` 文件：`MYSQL_PASSWORD=你的密码`
5. 执行 `sql/` 目录下的建表和数据预处理脚本
6. 运行主脚本：`python src/ab_test_analysis.py`