"""
淘宝AB测试 - t检验与卡方检验分析主脚本
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import chi2_contingency
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine
import os
import warnings

warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ============================================
# 配置参数
# ============================================
MYSQL_PASSWORD = "123456"  # ← 改成你的MySQL密码
ALPHA = 0.05
OUTPUT_PATH = "./output/"

engine = create_engine(
    f"mysql+pymysql://root:{MYSQL_PASSWORD}@localhost:3306/taobao_abtest?charset=utf8mb4"
)


def load_data():
    """从MySQL加载用户指标数据"""
    print("=" * 60)
    print("加载用户指标数据...")
    df = pd.read_sql("SELECT * FROM user_metrics", engine)
    print(f"✅ 共 {len(df)} 条用户记录")
    print(df['group_type'].value_counts())
    return df


def normality_test(data, sample_size=5000):
    """正态性检验"""
    n = len(data)
    if n <= 5000:
        stat, p_value = stats.shapiro(data)
        test_name = "Shapiro-Wilk"
    else:
        standardized = (data - np.mean(data)) / np.std(data)
        stat, p_value = stats.kstest(standardized, 'norm')
        test_name = "Kolmogorov-Smirnov"
    return test_name, stat, p_value


def levene_test(group_a, group_b):
    """方差齐性检验 (Levene检验)"""
    stat, p_value = stats.levene(group_a, group_b, center='median')
    return stat, p_value


def cohens_d(group_a, group_b):
    """计算Cohen's d效应量"""
    n1, n2 = len(group_a), len(group_b)
    pooled_std = np.sqrt(
        ((n1 - 1) * group_a.var() + (n2 - 1) * group_b.var()) / (n1 + n2 - 2)
    )
    d = (group_b.mean() - group_a.mean()) / pooled_std
    return d, pooled_std


def confidence_interval(diff, pooled_std, n1, n2, confidence=0.95):
    """计算置信区间"""
    se = pooled_std * np.sqrt(1 / n1 + 1 / n2)
    alpha = 1 - confidence
    z_score = stats.norm.ppf(1 - alpha / 2)
    margin = z_score * se
    return diff - margin, diff + margin


def perform_chi_square(df, metric_name, metric_col):
    """执行卡方检验（针对转化率类指标）"""
    print(f"\n{'=' * 60}")
    print(f"【{metric_name}】卡方检验分析")
    print(f"{'=' * 60}")

    # 将转化率转为0-1变量：大于0视为转化，等于0视为未转化
    df_copy = df.copy()
    df_copy['is_converted'] = (df_copy[metric_col] > 0).astype(int)

    # 构建列联表：分组 × 是否转化
    contingency = pd.crosstab(df_copy['group_type'], df_copy['is_converted'])

    # 确保列名为"未转化"和"转化"
    col_names = {0: '未转化', 1: '转化'}
    contingency = contingency.rename(columns=col_names)

    print(f"\n列联表:")
    print(contingency)
    print()

    # 计算转化率
    rate_A = df[df['group_type'] == 'A'][metric_col].mean()
    rate_B = df[df['group_type'] == 'B'][metric_col].mean()

    print(f"A组(对照) 转化率: {rate_A:.4f} ({rate_A * 100:.2f}%)")
    print(f"B组(实验) 转化率: {rate_B:.4f} ({rate_B * 100:.2f}%)")

    # 执行卡方检验
    chi2, p_value, dof, expected = chi2_contingency(contingency)

    print(f"\n--- 卡方检验结果 ---")
    print(f"χ²统计量 = {chi2:.4f}")
    print(f"p值 = {p_value:.6f}")
    print(f"自由度 = {dof}")

    print(f"\n期望频数:")
    expected_df = pd.DataFrame(expected,
                               columns=contingency.columns,
                               index=contingency.index)
    print(expected_df.round(2))

    # 结论
    print(f"\n--- 统计结论 ---")
    if p_value < ALPHA:
        conclusion = f"✅ 拒绝原假设 (p = {p_value:.4f} < {ALPHA})"
        print(conclusion)
        print(f"两组在【{metric_name}】上存在显著差异!")
        if rate_B > rate_A:
            print(f"实验组(B)转化率显著高于对照组(A)，提升幅度: {((rate_B / rate_A - 1) * 100):.2f}%")
        else:
            print(f"对照组(A)转化率显著高于实验组(B)")
    else:
        conclusion = f"❌ 无法拒绝原假设 (p = {p_value:.4f} >= {ALPHA})"
        print(conclusion)
        print(f"两组在【{metric_name}】上无显著差异")

    # 保存结果到MySQL
    result_df = pd.DataFrame([{
        'metric_name': metric_name,
        'test_type': 'chi_square',
        'group_a_mean': round(rate_A, 6),
        'group_b_mean': round(rate_B, 6),
        'group_a_std': None,
        'group_b_std': None,
        'group_a_n': int(contingency.loc['A'].sum()),
        'group_b_n': int(contingency.loc['B'].sum()),
        't_statistic': None,
        'p_value': round(p_value, 6),
        'cohens_d': None,
        'ci_lower': None,
        'ci_upper': None,
        'chi2_statistic': round(chi2, 6),
        'dof': dof,
        'conclusion': conclusion
    }])
    result_df.to_sql('ab_test_results', engine, if_exists='append', index=False)
    print(f"  → 结果已保存到MySQL")

    return {
        'metric': metric_name,
        'test_type': 'chi_square',
        'rate_a': rate_A, 'rate_b': rate_B,
        'chi2': chi2, 'p_value': p_value, 'dof': dof,
        'conclusion': conclusion
    }


def perform_ttest(df, metric_name, metric_col):
    """执行完整的t检验流程"""
    print(f"\n{'=' * 60}")
    print(f"【{metric_name}】t检验分析")
    print(f"{'=' * 60}")

    group_a = df[df['group_type'] == 'A'][metric_col].dropna()
    group_b = df[df['group_type'] == 'B'][metric_col].dropna()

    n_a, n_b = len(group_a), len(group_b)
    mean_a, mean_b = group_a.mean(), group_b.mean()
    std_a, std_b = group_a.std(), group_b.std()

    print(f"\nA组(对照组): n={n_a}, mean={mean_a:.6f}, std={std_a:.6f}")
    print(f"B组(实验组): n={n_b}, mean={mean_b:.6f}, std={std_b:.6f}")

    # 1. 正态性检验
    print(f"\n--- 1. 正态性检验 ---")
    test_name_a, stat_a, p_norm_a = normality_test(group_a)
    test_name_b, stat_b, p_norm_b = normality_test(group_b)
    print(f"A组 {test_name_a}: statistic={stat_a:.4f}, p={p_norm_a:.4f}")
    print(f"B组 {test_name_b}: statistic={stat_b:.4f}, p={p_norm_b:.4f}")

    if p_norm_a > ALPHA and p_norm_b > ALPHA:
        print(f"  → 两组数据均服从正态分布 (p > {ALPHA})")
    else:
        print(f"  ⚠️ 数据可能不服从正态分布，t检验结果需谨慎解释")

    # 2. 方差齐性检验
    print(f"\n--- 2. 方差齐性检验 (Levene) ---")
    levene_stat, p_levene = levene_test(group_a, group_b)
    print(f"Levene statistic={levene_stat:.4f}, p={p_levene:.4f}")

    equal_var = p_levene > ALPHA
    if equal_var:
        print(f"  → 方差齐性成立 (p > {ALPHA})，使用标准t检验")
    else:
        print(f"  → 方差不齐 (p <= {ALPHA})，使用Welch's t检验")

    # 3. 独立样本t检验
    print(f"\n--- 3. 独立样本t检验 ---")
    t_stat, p_value = stats.ttest_ind(group_a, group_b, equal_var=equal_var)
    print(f"t统计量 = {t_stat:.4f}")
    print(f"p值 = {p_value:.6f}")

    # 4. 效应量
    print(f"\n--- 4. 效应量分析 ---")
    d, pooled_std = cohens_d(group_a, group_b)
    print(f"Cohen's d = {d:.4f}")

    if abs(d) < 0.2:
        effect_size = "微小效应"
    elif abs(d) < 0.5:
        effect_size = "小效应"
    elif abs(d) < 0.8:
        effect_size = "中等效应"
    else:
        effect_size = "大效应"
    print(f"效应量解释: {effect_size}")

    # 5. 置信区间
    print(f"\n--- 5. 95%置信区间 ---")
    diff = mean_b - mean_a
    ci_lower, ci_upper = confidence_interval(diff, pooled_std, n_a, n_b)
    print(f"均值差异 (B - A) = {diff:.6f}")
    print(f"95% CI: [{ci_lower:.6f}, {ci_upper:.6f}]")

    # 6. 结论
    print(f"\n--- 6. 统计结论 ---")
    if p_value < ALPHA:
        conclusion = f"✅ 拒绝原假设 (p = {p_value:.4f} < {ALPHA})"
        print(conclusion)
        print(f"两组在【{metric_name}】上存在显著差异!")
        if mean_b > mean_a:
            print(f"实验组(B)显著高于对照组(A)，提升幅度: {((mean_b / mean_a - 1) * 100):.2f}%")
        else:
            print(f"对照组(A)显著高于实验组(B)")
    else:
        conclusion = f"❌ 无法拒绝原假设 (p = {p_value:.4f} >= {ALPHA})"
        print(conclusion)
        print(f"两组在【{metric_name}】上无显著差异")

    # 保存结果到MySQL
    result_df = pd.DataFrame([{
        'metric_name': metric_name,
        'test_type': 't_test',
        'group_a_mean': round(mean_a, 6),
        'group_b_mean': round(mean_b, 6),
        'group_a_std': round(std_a, 6),
        'group_b_std': round(std_b, 6),
        'group_a_n': n_a,
        'group_b_n': n_b,
        't_statistic': round(t_stat, 6),
        'p_value': round(p_value, 6),
        'cohens_d': round(d, 6),
        'ci_lower': round(ci_lower, 6),
        'ci_upper': round(ci_upper, 6),
        'chi2_statistic': None,
        'dof': None,
        'conclusion': conclusion
    }])
    result_df.to_sql('ab_test_results', engine, if_exists='append', index=False)
    print(f"  → 结果已保存到MySQL")

    return {
        'metric': metric_name,
        'test_type': 't_test',
        'mean_a': mean_a, 'mean_b': mean_b,
        'std_a': std_a, 'std_b': std_b,
        'n_a': n_a, 'n_b': n_b,
        't_stat': t_stat, 'p_value': p_value,
        'cohens_d': d, 'ci_lower': ci_lower, 'ci_upper': ci_upper,
        'conclusion': conclusion
    }


def visualize(df, t_results, chi_results, save_path='./output/'):
    """优化版可视化：生成5张高质量图表"""
    print(f"\n{'=' * 60}")
    print("生成可视化图表...")
    os.makedirs(save_path, exist_ok=True)

    colors = {'A': '#3498db', 'B': '#e74c3c'}

    # ========== 图1: 转化率密度分布 ==========
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle('淘宝AB测试 - 转化率分布对比', fontsize=16, fontweight='bold', y=1.02)

    for idx, (col, title) in enumerate([('conversion_rate', '购买转化率'), ('cart_rate', '加购转化率')]):
        ax = axes[idx]
        for g, label in [('A', 'A组(对照)'), ('B', 'B组(实验)')]:
            data = df[df['group_type'] == g][col].dropna()
            sns.kdeplot(data=data, ax=ax, label=label, color=colors[g],
                        fill=True, alpha=0.3, linewidth=2)
        ax.set_title(f'{title}分布密度', fontsize=13, fontweight='bold')
        ax.set_xlabel(title, fontsize=11)
        ax.set_ylabel('密度', fontsize=11)
        ax.legend(fontsize=10)
        ax.grid(axis='y', alpha=0.3)
        ax.set_xlim(0, min(0.5, df[col].quantile(0.99)))

    plt.tight_layout()
    plt.savefig(f'{save_path}fig1_conversion_kde.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ {save_path}fig1_conversion_kde.png")

    # ========== 图2: 行为次数小提琴图 ==========
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('淘宝AB测试 - 用户行为次数对比', fontsize=16, fontweight='bold', y=1.01)

    metrics = [('pv_count', '点击次数', '次'), ('buy_count', '购买次数', '次'),
               ('avg_pv_per_day', '日均点击', '次/天'), ('active_days', '活跃天数', '天')]

    for idx, (col, title, unit) in enumerate(metrics):
        ax = axes[idx // 2, idx % 2]
        group_a = df[df['group_type'] == 'A'][col].dropna()
        group_b = df[df['group_type'] == 'B'][col].dropna()

        parts = ax.violinplot([group_a.values, group_b.values],
                              positions=[1, 2], showmeans=False, showmedians=False)
        for pc, color in zip(parts['bodies'], ['#3498db', '#e74c3c']):
            pc.set_facecolor(color)
            pc.set_alpha(0.3)

        bp = ax.boxplot([group_a.values, group_b.values],
                        positions=[1, 2], widths=0.15,
                        patch_artist=True, showfliers=False)
        for patch, color in zip(bp['boxes'], ['#3498db', '#e74c3c']):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_xticks([1, 2])
        ax.set_xticklabels(['A组(对照)', 'B组(实验)'], fontsize=11)
        ax.set_title(title, fontsize=13, fontweight='bold')
        ax.set_ylabel(f'数值 ({unit})', fontsize=11)
        ax.grid(axis='y', alpha=0.3)
        ax.text(1, group_a.mean(), f'均值:{group_a.mean():.1f}',
                ha='center', va='bottom', fontsize=9, color='#3498db', fontweight='bold')
        ax.text(2, group_b.mean(), f'均值:{group_b.mean():.1f}',
                ha='center', va='bottom', fontsize=9, color='#e74c3c', fontweight='bold')

    plt.tight_layout()
    plt.savefig(f'{save_path}fig2_behavior_violin.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ {save_path}fig2_behavior_violin.png")

    # ========== 图3: t检验结果汇总表 ==========
    fig, ax = plt.subplots(figsize=(14, 5))

    columns = ['指标', 'A组均值', 'B组均值', 't统计量', 'p值', "Cohen's d", '结论']
    table_data = []
    for r in t_results:
        table_data.append([
            r['metric'],
            f"{r['mean_a']:.4f}",
            f"{r['mean_b']:.4f}",
            f"{r['t_stat']:.4f}",
            f"{r['p_value']:.4f}",
            f"{r['cohens_d']:.4f}",
            '❌ 不显著' if r['p_value'] >= 0.05 else '✅ 显著'
        ])

    table = ax.table(cellText=table_data, colLabels=columns,
                     cellLoc='center', loc='center',
                     colWidths=[0.16, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12])
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 2.2)

    for i in range(len(columns)):
        table[(0, i)].set_facecolor('#2c3e50')
        table[(0, i)].set_text_props(weight='bold', color='white')

    for i in range(1, len(table_data) + 1):
        for j in range(len(columns)):
            table[(i, j)].set_facecolor('#ecf0f1' if i % 2 == 0 else '#ffffff')
        p_val = float(table_data[i - 1][4])
        bg = '#d5f5e3' if p_val < 0.05 else '#fadbd8'
        table[(i, 4)].set_facecolor(bg)
        table[(i, 6)].set_facecolor(bg)

    ax.axis('off')
    ax.set_title('淘宝AB测试 - t检验结果汇总表', fontsize=16, fontweight='bold', pad=20)
    plt.tight_layout()
    plt.savefig(f'{save_path}fig3_results_table.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ {save_path}fig3_results_table.png")

    # ========== 图4: 均值差异置信区间 ==========
    fig, ax = plt.subplots(figsize=(12, 6))

    metrics = [r['metric'] for r in t_results]
    diffs = [r['mean_b'] - r['mean_a'] for r in t_results]
    ci_lower = [r['ci_lower'] for r in t_results]
    ci_upper = [r['ci_upper'] for r in t_results]

    y_pos = np.arange(len(metrics))
    bar_colors = ['#e74c3c' if d > 0 else '#3498db' for d in diffs]

    ax.barh(y_pos, diffs, color=bar_colors, alpha=0.7, height=0.6)

    for i, (d, cl, cu) in enumerate(zip(diffs, ci_lower, ci_upper)):
        ax.plot([cl, cu], [i, i], 'k-', linewidth=2)
        ax.plot([cl, cl], [i - 0.1, i + 0.1], 'k-', linewidth=2)
        ax.plot([cu, cu], [i - 0.1, i + 0.1], 'k-', linewidth=2)
        ax.text(d, i + 0.25, f'{d:.4f}', ha='center', va='bottom',
                fontsize=9, fontweight='bold')

    ax.set_yticks(y_pos)
    ax.set_yticklabels(metrics, fontsize=12)
    ax.axvline(x=0, color='black', linewidth=1, linestyle='--')
    ax.set_xlabel('均值差异 (B组 - A组)', fontsize=12)
    ax.set_title('AB测试 - 各指标均值差异及95%置信区间', fontsize=14, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#e74c3c', alpha=0.7, label='B组 > A组'),
        Patch(facecolor='#3498db', alpha=0.7, label='B组 < A组'),
        plt.Line2D([0], [0], color='black', linewidth=2, label='95% CI')
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=10)

    plt.tight_layout()
    plt.savefig(f'{save_path}fig4_mean_diff_ci.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ {save_path}fig4_mean_diff_ci.png")

    # ========== 新增图5: 卡方检验结果汇总表 ==========
    if chi_results:
        fig, ax = plt.subplots(figsize=(12, 3))

        columns = ['指标', 'A组转化率', 'B组转化率', 'χ²统计量', 'p值', '结论']
        table_data = []
        for r in chi_results:
            table_data.append([
                r['metric'],
                f"{r['rate_a']:.4f}",
                f"{r['rate_b']:.4f}",
                f"{r['chi2']:.4f}",
                f"{r['p_value']:.4f}",
                '❌ 不显著' if r['p_value'] >= 0.05 else '✅ 显著'
            ])

        table = ax.table(cellText=table_data, colLabels=columns,
                         cellLoc='center', loc='center',
                         colWidths=[0.18, 0.15, 0.15, 0.15, 0.15, 0.12])
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1.2, 2.5)

        for i in range(len(columns)):
            table[(0, i)].set_facecolor('#2c3e50')
            table[(0, i)].set_text_props(weight='bold', color='white')

        for i in range(1, len(table_data) + 1):
            for j in range(len(columns)):
                table[(i, j)].set_facecolor('#ecf0f1' if i % 2 == 0 else '#ffffff')
            p_val = float(table_data[i - 1][4])
            bg = '#d5f5e3' if p_val < 0.05 else '#fadbd8'
            table[(i, 4)].set_facecolor(bg)
            table[(i, 5)].set_facecolor(bg)

        ax.axis('off')
        ax.set_title('淘宝AB测试 - 卡方检验结果汇总表', fontsize=16, fontweight='bold', pad=20)
        plt.tight_layout()
        plt.savefig(f'{save_path}fig5_chi_square_table.png', dpi=150, bbox_inches='tight')
        plt.close()
        print(f"✅ {save_path}fig5_chi_square_table.png")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("淘宝AB测试")
    print("=" * 60)

    df = load_data()

    # ========== 卡方检验（针对0-1转化率类指标）==========
    print("\n" + "=" * 60)
    print("开始卡方检验（转化率类指标）")
    print("=" * 60)

    chi_metrics = [
        ('购买转化率', 'conversion_rate'),
        ('加购转化率', 'cart_rate')
    ]

    chi_results = []
    for metric_name, metric_col in chi_metrics:
        result = perform_chi_square(df, metric_name, metric_col)
        chi_results.append(result)

    # ========== t检验（针对连续型指标）==========
    print("\n" + "=" * 60)
    print("开始t检验（连续型指标）")
    print("=" * 60)

    t_metrics = [
        ('购买转化率', 'conversion_rate'),
        ('加购转化率', 'cart_rate'),
        ('点击次数', 'pv_count'),
        ('购买次数', 'buy_count'),
        ('日均点击', 'avg_pv_per_day'),
        ('活跃天数', 'active_days')
    ]

    t_results = []
    for metric_name, metric_col in t_metrics:
        result = perform_ttest(df, metric_name, metric_col)
        t_results.append(result)

    # 可视化
    visualize(df, t_results, chi_results, OUTPUT_PATH)

    print(f"\n{'=' * 60}")
    print("AB测试分析全部完成!")
    print(f"结果保存在: {OUTPUT_PATH}")
    print(f"MySQL表: ab_test_results")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
