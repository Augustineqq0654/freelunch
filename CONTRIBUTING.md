# 贡献指南

两种贡献，都不需要写代码。**把一条过期资源标出来，和新增一条同样有价值。**

## 一、核验一条已有资源（最受欢迎）

当前待核验的条目见 `python scripts/build.py --stale` 的输出。

步骤：

1. 打开该条目 `verification.evidence` 里的官方链接
2. 对照页面，确认这几件事还成立：免费额度数值、覆盖的模型、是否需要绑卡/实名/手机
3. 修改 `data/llm-api/<id>.yaml`：

```yaml
verification:
  method: manual
  checked_at: 2026-11-20      # 你实际查看的日期
  evidence: https://官方文档链接
```

4. 顺带补上 `cn_access`：你在国内网络下实测的结果（`direct` / `partial` / `blocked`）

如果结论是「它已经不免费了」或「服务已下线」，不要直接删文件，改成：

```yaml
archived: true
archived_reason: 2026-08-01 起取消免费额度，改为充值后按量计费
```

PR 描述里写一句「原额度 X，现为 Y，依据 <链接>」就够了。

## 二、新增一条资源

1. 复制模板：`cp data/llm-api/_template.yaml data/llm-api/你的-id.yaml`
2. 文件名 = `id`，小写短横线，例如 `my-provider.yaml`
3. 按模板里的注释填，字段含义见 [POLICY.md](docs/POLICY.md)。需要实名/手机才能注册的国内服务**同样收**：`requirements` 里如实填 `true`，构建时会自动进「需实名/手机」二级表
4. 本地跑一次：

```bash
python scripts/build.py
```

只要有一条不合规（比如把 `credit_card` 填成 `true`、或者填了 `checked_at` 却没给 `evidence`），构建会直接失败并告诉你哪一行错了。

5. 提交 PR，说明你是**怎么验证**的。附 `curl` 输出、控制台截图、或官方文档摘录，三选一即可。

## 提交前自查

- [ ] 这家确实是**长期免费**，不是注册赠金或限时活动
- [ ] 确实**不要信用卡、不要邀请码**；需要实名/手机才能注册的也收，但 `requirements` 要如实填，让条目进二级表
- [ ] 是服务商**官方**渠道，不是中转站、反代或逆向接口
- [ ] `verification.checked_at` 是我**今天实际查看**的日期，不是抄来的
- [ ] `verification.evidence` 指向官方页面，链接能打开
- [ ] 免费额度只写**真正免费覆盖的模型**，没把付费模型算进去
- [ ] 跑过 `python scripts/build.py`，没有报错

## 不会被合并的 PR

- 只改 README.md（它是生成物，改了也会被 CI 打回）
- 加邀请链接、返利链接、自建中转站
- 把付费服务写成"免费"，或把试用额度当长期免费
- 没有任何验证依据，只凭印象填写

## 发现规则本身有问题？

规则写得不对、或者某条排除判断过时了，欢迎开 issue 讨论。**规则是可以改的，但要有理由。**
