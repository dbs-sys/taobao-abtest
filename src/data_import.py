"""
淘宝AB测试 - 数据导入MySQL
"""

import pandas as pd
from sqlalchemy import create_engine
import os
from sqlalchemy import create_engine, text


MYSQL_PASSWORD = "123456"  # 你的密码
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "UserBehavior.csv")


def main():
    print("=" * 50)
    print("淘宝AB测试 - 数据导入")
    print("=" * 50)

    engine = create_engine(
        f"mysql+pymysql://root:{MYSQL_PASSWORD}@localhost:3306/taobao_abtest?charset=utf8mb4"
    )

    # 清空已有数据（防止重复导入报错）
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE user_behavior"))
        print("已清空 user_behavior 表")

    print(f"读取CSV: {CSV_PATH}")

    # 有表头，直接读取
    df = pd.read_csv(CSV_PATH, nrows=1000000, low_memory=False)

    print(f"原始列名: {df.columns.tolist()}")
    print(f"共 {len(df)} 行")
    print(f"behavior_type唯一值: {sorted(df['behavior_type'].unique())}")

    # 重命名列
    df = df.rename(columns={
        'item_category': 'category_id',
        'time': 'behavior_datetime'
    })

    # behavior_type 数字转字符串
    behavior_map = {1: 'pv', 2: 'buy', 3: 'fav', 4: 'cart'}
    df['behavior_type'] = df['behavior_type'].map(behavior_map)

    # 时间转换（格式: 2014-12-06 02）
    df['behavior_datetime'] = pd.to_datetime(df['behavior_datetime'], format='%Y-%m-%d %H', errors='coerce')
    df['behavior_date'] = df['behavior_datetime'].dt.date
    df['behavior_hour'] = df['behavior_datetime'].dt.hour

    # 添加 ts 字段（时间戳秒数）
    df['ts'] = df['behavior_datetime'].astype('int64') // 10 ** 9

    # 删除无法转换的行
    df = df.dropna(subset=['behavior_datetime', 'behavior_type'])

    # 选择需要的列
    df = df[['user_id', 'item_id', 'category_id', 'behavior_type', 'ts',
             'behavior_datetime', 'behavior_date', 'behavior_hour']]

    print(f"\n预处理后: {len(df)} 行")
    print(f"behavior_type分布:\n{df['behavior_type'].value_counts()}")

    print("\n导入MySQL...")
    df = df.drop_duplicates(subset=['user_id', 'item_id', 'behavior_type', 'ts'])
    print(f"去重后: {len(df)} 行")

    df.to_sql('user_behavior', engine, if_exists='append', index=False, chunksize=20000)

    result = pd.read_sql("SELECT COUNT(*) AS total FROM user_behavior", engine)
    print(f"\n✅ 导入完成! 表中总记录: {result['total'][0]}")


if __name__ == '__main__':
    main()
