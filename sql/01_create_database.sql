-- ============================================
-- 淘宝AB测试项目 - MySQL建表脚本
-- 技术栈: PyCharm + MySQL + Python t检验
-- ============================================

-- 1. 创建数据库
CREATE DATABASE IF NOT EXISTS taobao_abtest
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE taobao_abtest;

-- 2. 用户行为原始数据表
DROP TABLE IF EXISTS user_behavior;
CREATE TABLE user_behavior (
    user_id BIGINT COMMENT '用户ID(脱敏)',
    item_id BIGINT COMMENT '商品ID(脱敏)',
    category_id INT COMMENT '商品类目ID',
    behavior_type VARCHAR(10) COMMENT '行为类型: pv/buy/cart/fav',
    ts INT COMMENT '行为时间戳(秒)',
    behavior_datetime DATETIME COMMENT '行为日期时间',
    behavior_date DATE COMMENT '行为日期',
    behavior_hour INT COMMENT '行为小时',
    PRIMARY KEY (user_id, item_id, behavior_type, ts),
    INDEX idx_user_id (user_id),
    INDEX idx_behavior_type (behavior_type),
    INDEX idx_behavior_date (behavior_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='淘宝用户行为原始数据';

-- 3. AB分组表
DROP TABLE IF EXISTS ab_groups;
CREATE TABLE ab_groups (
    user_id BIGINT PRIMARY KEY COMMENT '用户ID',
    group_type CHAR(1) COMMENT 'A=对照组, B=实验组',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. 用户核心指标表
DROP TABLE IF EXISTS user_metrics;
CREATE TABLE user_metrics (
    user_id BIGINT PRIMARY KEY COMMENT '用户ID',
    group_type CHAR(1) COMMENT '分组',
    pv_count INT DEFAULT 0 COMMENT '点击次数',
    buy_count INT DEFAULT 0 COMMENT '购买次数',
    cart_count INT DEFAULT 0 COMMENT '加购次数',
    fav_count INT DEFAULT 0 COMMENT '收藏次数',
    conversion_rate DECIMAL(10,6) DEFAULT 0 COMMENT '购买转化率',
    cart_rate DECIMAL(10,6) DEFAULT 0 COMMENT '加购转化率',
    avg_pv_per_day DECIMAL(10,2) DEFAULT 0 COMMENT '日均点击',
    active_days INT DEFAULT 0 COMMENT '活跃天数',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户核心指标';

-- 5. AB测试结果表
DROP TABLE IF EXISTS ab_test_results;
CREATE TABLE ab_test_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    metric_name VARCHAR(50) COMMENT '指标名称',
    group_a_mean DECIMAL(10,6), group_b_mean DECIMAL(10,6),
    group_a_std DECIMAL(10,6), group_b_std DECIMAL(10,6),
    group_a_n INT, group_b_n INT,
    t_statistic DECIMAL(10,6), p_value DECIMAL(10,6),
    cohens_d DECIMAL(10,6),
    ci_lower DECIMAL(10,6), ci_upper DECIMAL(10,6),
    conclusion VARCHAR(200),
    test_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SELECT '数据库初始化完成!' AS status;
