# 美股日线采集

独立采集美股日线，供财报筛选程序读取。通过 Nasdaq 官方证券目录获取名单，使用腾讯搜索匹配证券代码，再请求历史日线。

## 当前行为

- 入口：`app/batch_price_run.py`。
- 默认仅处理名单前 100 只证券，每只间隔 1 秒；这是测试配置，不是全市场配置。
- 保存最近 30 个已收盘交易日，采用 NYSE 日历和收盘后 5 分钟缓冲。
- 请求前复权日线；接口字段和复权规则仍需在正式研究使用前核验。
- 腾讯不保证覆盖全部证券。代码匹配失败、历史条数不足或交易日期缺失时，记录失败并继续处理后续证券。
- CSV 使用临时文件完成写入后替换。失败时旧 CSV 可能保留，读取方应同时检查批次状态及数据日期。
- 缓存成功匹配的代码，默认有效期为 30 天。
- 只输出终端日志，不创建日志文件。代码映射缓存、行情及批次状态均在 output 下，不提交 Git。

## Ubuntu 安装与运行

以下操作在服务器执行：

```bash
cd /root
 git clone https://github.com/Levi-Pan/market_data_collector.git
cd /root/market_data_collector
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app/batch_price_run.py
```

私有仓库克隆需要配置 GitHub SSH 密钥或 HTTPS 凭据。若系统缺少 venv 模块，先安装系统软件包 python3-venv。

## 输出

- `output/universe.csv`：官方证券名单，包含股票、ETF 及其他证券类型。
- `output/us_daily/<symbol>.csv`：每只证券最近 30 个完整交易日。
- `output/symbol_mapping.sqlite3`：证券代码匹配缓存。
- `output/batch_state.json`：批次目标日期、成功和失败明细。

退出码：0 表示本批全部成功，2 表示本批存在失败，1 表示入口遇到未处理异常。

## 配置与限制

配置位于 standard_module/config.py，路径根据项目位置自动生成，可在 Windows 和 Linux 运行。

当前仍为小批量验证版本：尚未实现任务互斥、断点续采和明确的全市场开关。批次状态在开始和结束时写入；进程被强制终止时，状态可能停留在 RUNNING。不要同时启动多个批次。

应用输出采用统一交易日期窗口；停牌或历史不足的证券会被严格校验拒绝。官方名单和腾讯覆盖范围不同，不能把本程序当作无缺失的全市场行情源。
