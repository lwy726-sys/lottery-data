# -*- coding: utf-8 -*-
"""
彩票开奖数据抓取脚本
- 数据源：500彩票网（datachart.500.com）
- 支持：双色球、大乐透、排列五
- 输出：data/ssq.json、data/dlt.json、data/pl5.json
"""
import json
import re
import os
import time
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# 请求头（模拟浏览器，避免被拒绝）
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

# 数据源 URL
SOURCES = {
    'ssq': 'https://datachart.500.com/ssq/history/newinc/history.php?start=03001&end=99999',
    'dlt': 'https://datachart.500.com/dlt/history/newinc/history.php?start=07001&end=99999',
    'pl5': 'https://datachart.500.com/pl5/history/newinc/history.php?start=07001&end=99999',
}


def fetch_draw(lt, url, retry=3):
    """
    抓取单个彩种的开奖数据
    :param lt: 彩种代码（ssq/dlt/pl5）
    :param url: 数据源 URL
    :param retry: 重试次数
    :return: 数据列表
    """
    for attempt in range(retry):
        try:
            print(f'[{lt}] 第 {attempt + 1} 次尝试抓取...')
            resp = requests.get(url, headers=HEADERS, timeout=25)
            if resp.status_code != 200:
                print(f'[{lt}] HTTP {resp.status_code}')
                time.sleep(3)
                continue

            # 500彩票网使用 GBK 编码
            resp.encoding = 'gbk'
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 数据在 tbody#tdata 的 tr 行中
            rows = soup.select('tbody#tdata tr')
            if not rows:
                print(f'[{lt}] 未找到数据表格')
                time.sleep(3)
                continue

            out = []
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 6:
                    continue

                # 期号
                issue = cells[0].text.strip()
                if not re.match(r'^\d{3,10}$', issue):
                    continue

                # 号码（根据彩种不同）
                if lt == 'ssq':
                    # 双色球：6 红 + 1 蓝
                    nums = [cells[i].text.strip() for i in range(1, 8)]
                    front_count, back_count = 6, 1
                elif lt == 'dlt':
                    # 大乐透：5 前 + 2 后
                    nums = [cells[i].text.strip() for i in range(1, 8)]
                    front_count, back_count = 5, 2
                else:
                    # 排列五：5 位数字
                    nums = [cells[i].text.strip() for i in range(1, 6)]
                    front_count, back_count = 5, 0

                # 号码转为整数
                try:
                    nums_int = [int(x) for x in nums]
                except (ValueError, TypeError):
                    continue

                # 开奖日期
                date = ''
                for c in cells:
                    t = c.text.strip()
                    if re.match(r'^\d{4}-\d{2}-\d{2}', t):
                        date = t[:10]
                        break

                # 拆分前区/后区
                front = sorted(nums_int[:front_count])
                back = sorted(nums_int[front_count:front_count + back_count]) if back_count else []

                out.append({
                    'issue': issue,
                    'front': front,
                    'back': back,
                    'date': date,
                })

            if out:
                print(f'[{lt}] 成功抓取 {len(out)} 期')
                return out

        except requests.exceptions.Timeout:
            print(f'[{lt}] 请求超时')
        except requests.exceptions.RequestException as e:
            print(f'[{lt}] 请求异常：{e}')
        except Exception as e:
            print(f'[{lt}] 解析异常：{e}')

        # 重试前等待
        if attempt < retry - 1:
            time.sleep(3)

    print(f'[{lt}] 全部重试失败')
    return []


def deduplicate(draws):
    """
    去重：同期号只保留一条
    """
    seen = {}
    for d in draws:
        key = d['issue']
        if key not in seen:
            seen[key] = d
        else:
            # 保留有日期的
            if d.get('date') and not seen[key].get('date'):
                seen[key] = d
    # 按期号排序
    return sorted(seen.values(), key=lambda x: int(x['issue']))


def main():
    """主函数"""
    print('=' * 50)
    print(f'开始抓取 · {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 50)

    # 创建 data 目录
    os.makedirs('data', exist_ok=True)

    success_count = 0
    for lt, url in SOURCES.items():
        print(f'\n--- 抓取 {lt} ---')
        draws = fetch_draw(lt, url)

        if not draws:
            print(f'[{lt}] 无数据，跳过')
            continue

        # 去重
        draws = deduplicate(draws)

        # 只保留最近 1000 期，避免文件过大
        draws = draws[-1000:]

        # 写入 JSON 文件
        output = {
            'lottery': lt,
            'updateTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'count': len(draws),
            'draws': draws,
        }

        filepath = f'data/{lt}.json'
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f'[{lt}] 已保存 {len(draws)} 期到 {filepath}')
        success_count += 1

    print('\n' + '=' * 50)
    print(f'抓取完成 · 成功 {success_count} 个彩种')
    print('=' * 50)

    # 如果全部失败，返回非零退出码（让 Actions 报错）
    if success_count == 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
