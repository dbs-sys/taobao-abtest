-- ============================================
-- 数据预处理: 生成AB分组 + 计算用户指标
-- ============================================

USE taobao_abtest;

-- 先清空旧数据（防止重复执行报错）
TRUNCATE TABLE ab_groups;
TRUNCATE TABLE user_metrics;

-- 步骤1: AB随机分组 (按user_id奇偶性)
INSERT INTO ab_groups (user_id, group_type)
SELECT DISTINCT user_id,
    CASE WHEN MOD(user_id, 2) = 0 THEN 'A' ELSE 'B' END
FROM user_behavior;

-- 验证分组均衡性
SELECT group_type, COUNT(*) AS user_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM ab_groups), 2) AS pct
FROM ab_groups GROUP BY group_type;

-- 步骤2: 计算每个用户的核心指标
INSERT INTO user_metrics (
    user_id, group_type, pv_count, buy_count, cart_count, fav_count,
    conversion_rate, cart_rate, avg_pv_per_day, active_days
)
SELECT
    ub.user_id, ag.group_type,
    COUNT(DISTINCT CASE WHEN behavior_type='pv' THEN CONCAT(item_id,'_',ts) END) AS pv_count,
    COUNT(DISTINCT CASE WHEN behavior_type='buy' THEN CONCAT(item_id,'_',ts) END) AS buy_count,
    COUNT(DISTINCT CASE WHEN behavior_type='cart' THEN CONCAT(item_id,'_',ts) END) AS cart_count,
    COUNT(DISTINCT CASE WHEN behavior_type='fav' THEN CONCAT(item_id,'_',ts) END) AS fav_count,
    CASE WHEN COUNT(CASE WHEN behavior_type='pv' THEN 1 END) = 0 THEN 0
         ELSE COUNT(CASE WHEN behavior_type='buy' THEN 1 END) * 1.0
              / COUNT(CASE WHEN behavior_type='pv' THEN 1 END) END AS conversion_rate,
    CASE WHEN COUNT(CASE WHEN behavior_type='pv' THEN 1 END) = 0 THEN 0
         ELSE COUNT(CASE WHEN behavior_type='cart' THEN 1 END) * 1.0
              / COUNT(CASE WHEN behavior_type='pv' THEN 1 END) END AS cart_rate,
    ROUND(COUNT(CASE WHEN behavior_type='pv' THEN 1 END) * 1.0
          / NULLIF(COUNT(DISTINCT behavior_date), 0), 2) AS avg_pv_per_day,
    COUNT(DISTINCT behavior_date) AS active_days
FROM user_behavior ub
JOIN ab_groups ag ON ub.user_id = ag.user_id
GROUP BY ub.user_id, ag.group_type;

-- 步骤3: 实验前均衡性检验
SELECT '实验前均衡性' AS check_type, group_type,
    COUNT(*) AS n,
    ROUND(AVG(pv_count), 2) AS avg_pv,
    ROUND(AVG(buy_count), 4) AS avg_buy,
    ROUND(AVG(conversion_rate), 6) AS avg_conversion,
    ROUND(AVG(active_days), 2) AS avg_active_days
FROM user_metrics GROUP BY group_type;

SELECT '数据预处理完成!' AS status;
