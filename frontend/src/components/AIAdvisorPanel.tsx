import {
  useEffect,
  useMemo,
  useState,
} from 'react'

import './AIAdvisorPanel.css'


type AdvisorRecord = {
  index: number
  action: string | null
  status: string | null
  fast_decision: string | null
  selected_planner: string | null
  rag_enabled: boolean
  rag_used: boolean
  rag_chunk_ids: string[]
  rag_retrieval_latency_s: number | null
  advisor_latency_s: number | null
  background_latency_s: number | null
  severity: string | null
  confidence: number | null
  error_type: string | null
}


type RagEvaluation = {
  mission_id: string | null

  advisor_record_count: number
  advisor_completed_count: number
  advisor_failed_count: number
  advisor_success_rate: number | null

  rag: {
    enabled_count: number
    used_count: number
    usage_rate: number | null
    failure_count: number
  }

  advisor_latency: {
    count: number
    mean_s: number | null
    min_s: number | null
    max_s: number | null
  }

  safety_consistency: {
    fast_decision_comparable: number
    fast_decision_matches: number
    fast_decision_match_rate: number | null

    selected_planner_comparable: number
    selected_planner_matches: number
    selected_planner_match_rate: number | null
  }

  advisor_records: AdvisorRecord[]
}


type MultiReplanEvaluation = {
  overall?: {
    mean_fast_decision_latency_s?: number | null
    max_fast_decision_latency_s?: number | null

    advisor_completed_count?: number
    advisor_failed_or_timeout_count?: number
  }
}


type RunDetailResponse = {
  summaries?: {
    rag_advisor_evaluation?: RagEvaluation
    multi_replan_evaluation?: MultiReplanEvaluation
  }
}


type Props = {
  runId: string | null
}


function numberValue(
  value: number | null | undefined,
  digits = 2,
) {
  if (
    value === null ||
    value === undefined
  ) {
    return '--'
  }

  return value.toFixed(digits)
}


function percentValue(
  value: number | null | undefined,
) {
  if (
    value === null ||
    value === undefined
  ) {
    return '--'
  }

  return `${(
    value * 100
  ).toFixed(0)}%`
}


function AIAdvisorPanel(
  {
    runId,
  }: Props,
) {
  const [data, setData] =
    useState<RunDetailResponse | null>(
      null,
    )

  const [loading, setLoading] =
    useState(false)

  const [error, setError] =
    useState<string | null>(null)


  useEffect(() => {
    if (!runId) {
      return
    }

    async function loadAdvisor() {
      try {
        setLoading(true)
        setError(null)

        const response = await fetch(
          `/runs/${runId}`,
        )

        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}`,
          )
        }

        const result =
          (await response.json()) as
            RunDetailResponse

        setData(result)
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Unknown error',
        )
      } finally {
        setLoading(false)
      }
    }

    loadAdvisor()
  }, [runId])


  const ragEvaluation =
    data?.summaries
      ?.rag_advisor_evaluation


  const multiReplan =
    data?.summaries
      ?.multi_replan_evaluation


  const fastPolicyMeanMs =
    useMemo(() => {
      const latency =
        multiReplan?.overall
          ?.mean_fast_decision_latency_s

      if (
        latency === null ||
        latency === undefined
      ) {
        return null
      }

      return latency * 1000
    }, [multiReplan])


  if (!runId) {
    return null
  }


  if (loading) {
    return (
      <section className="advisor-panel">
        <div className="advisor-message">
          正在加载 AI / RAG 智能顾问数据...
        </div>
      </section>
    )
  }


  if (error) {
    return (
      <section className="advisor-panel">
        <div className="advisor-message advisor-message-error">
          AI 智能顾问数据加载失败：
          {' '}
          {error}
        </div>
      </section>
    )
  }


  if (!ragEvaluation) {
    return (
      <section className="advisor-panel">
        <div className="advisor-message">
          当前任务暂无 AI / RAG 智能顾问评估数据
        </div>
      </section>
    )
  }


  const advisorFailed =
    ragEvaluation.advisor_failed_count > 0


  const ragUsed =
    ragEvaluation.rag.used_count > 0


  return (
    <section className="advisor-panel">

      <div className="advisor-header">

        <div>
          <h2>
            AI / RAG 智能顾问
          </h2>

          <p>
            大模型旁路分析、RAG 检索与安全一致性评估
          </p>
        </div>

        <div
          className={
            advisorFailed
              ? 'advisor-main-status failed'
              : 'advisor-main-status healthy'
          }
        >
          <span />

          {advisorFailed
            ? '部分调用失败'
            : '运行正常'}
        </div>

      </div>


      <div className="advisor-kpi-grid">

        <article className="advisor-kpi">

          <span>
            Advisor 调用次数
          </span>

          <strong>
            {ragEvaluation
              .advisor_record_count}
          </strong>

          <small>
            后台异步分析
          </small>

        </article>


        <article className="advisor-kpi">

          <span>
            成功次数
          </span>

          <strong>
            {ragEvaluation
              .advisor_completed_count}
          </strong>

          <small>
            成功率
            {' '}
            {percentValue(
              ragEvaluation
                .advisor_success_rate,
            )}
          </small>

        </article>


        <article className="advisor-kpi">

          <span>
            失败 / 超时
          </span>

          <strong
            className={
              advisorFailed
                ? 'danger-value'
                : ''
            }
          >
            {ragEvaluation
              .advisor_failed_count}
          </strong>

          <small>
            不阻断实时控制
          </small>

        </article>


        <article className="advisor-kpi">

          <span>
            Advisor 平均延迟
          </span>

          <strong>
            {numberValue(
              ragEvaluation
                .advisor_latency.mean_s,
              2,
            )}
            {' '}
            s
          </strong>

          <small>
            后台分析耗时
          </small>

        </article>


        <article className="advisor-kpi">

          <span>
            Fast Policy 一致率
          </span>

          <strong>
            {percentValue(
              ragEvaluation
                .safety_consistency
                .fast_decision_match_rate,
            )}
          </strong>

          <small>
            Advisor 与实时决策一致性
          </small>

        </article>


        <article className="advisor-kpi">

          <span>
            RAG 使用状态
          </span>

          <strong
            className={
              ragUsed
                ? 'rag-active'
                : ''
            }
          >
            {ragUsed
              ? '已使用'
              : '当前未使用'}
          </strong>

          <small>
            检索次数：
            {' '}
            {ragEvaluation
              .rag.used_count}
          </small>

        </article>

      </div>


      <div className="advisor-content-grid">


        <article className="advisor-architecture-card">

          <div className="advisor-subtitle">
            决策架构
          </div>


          <div className="architecture-flow">

            <div className="architecture-node fast">

              <div className="architecture-node-head">
                Fast Policy
              </div>

              <strong>
                实时安全决策主链路
              </strong>

              <span>
                平均决策延迟
                {' '}
                {numberValue(
                  fastPolicyMeanMs,
                  3,
                )}
                {' '}
                ms
              </span>

              <p>
                负责通信退化检测后的快速航迹决策，
                不依赖大模型返回结果。
              </p>

            </div>


            <div className="architecture-divider">
              +
            </div>


            <div className="architecture-node ai">

              <div className="architecture-node-head">
                AI / RAG Advisor
              </div>

              <strong>
                旁路解释与辅助分析
              </strong>

              <span>
                平均响应
                {' '}
                {numberValue(
                  ragEvaluation
                    .advisor_latency.mean_s,
                  2,
                )}
                {' '}
                s
              </span>

              <p>
                用于事件解释、风险分析和辅助建议；
                调用失败不会阻断无人机控制。
              </p>

            </div>

          </div>


          <div className="architecture-note">

            <span className="architecture-note-icon">
              ✓
            </span>

            <div>
              <strong>
                安全解耦
              </strong>

              <p>
                Fast Policy 负责实时控制，
                AI / RAG 模块负责非阻塞式智能分析。
              </p>
            </div>

          </div>

        </article>


        <article className="advisor-records-card">

          <div className="advisor-subtitle">
            Advisor 调用记录
          </div>


          <div className="advisor-record-list">

            {ragEvaluation
              .advisor_records
              .map(
                record => (
                  <div
                    className="advisor-record"
                    key={record.index}
                  >

                    <div className="advisor-record-index">
                      {record.index}
                    </div>


                    <div className="advisor-record-main">

                      <div className="advisor-record-title">

                        <strong>
                          第 {record.index} 次智能分析
                        </strong>

                        <span
                          className={
                            record.status ===
                              'FAILED'
                              ? 'record-status failed'
                              : 'record-status completed'
                          }
                        >
                          {record.status ===
                            'FAILED'
                            ? '失败 / 超时'
                            : '完成'}
                        </span>

                      </div>


                      <div className="advisor-record-details">

                        <span>
                          Fast Policy：
                          {record.fast_decision ??
                            '--'}
                        </span>

                        <span>
                          规划器：
                          {record.selected_planner ===
                            'communication_aware'
                            ? '通信感知规划器'
                            : record.selected_planner ??
                              '--'}
                        </span>

                        <span>
                          Advisor 延迟：
                          {numberValue(
                            record
                              .advisor_latency_s,
                            2,
                          )}
                          {' '}
                          s
                        </span>

                        <span>
                          RAG：
                          {record.rag_used
                            ? '已使用'
                            : '未使用'}
                        </span>

                      </div>


                      {record.error_type && (
                        <div className="advisor-error-row">

                          <span>
                            错误类型
                          </span>

                          <code>
                            {record.error_type}
                          </code>

                        </div>
                      )}

                    </div>

                  </div>
                ),
              )}

          </div>

        </article>

      </div>

    </section>
  )
}


export default AIAdvisorPanel
