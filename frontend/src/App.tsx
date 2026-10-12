import { Suspense, lazy, useEffect, useState } from 'react'
import './App.css'
import TrajectoryCoverage from './components/TrajectoryCoverage'
import IncidentTimeline from './components/IncidentTimeline'


const CommunicationCharts = lazy(
  () =>
    import(
      './components/CommunicationCharts'
    ),
)

const AIAdvisorPanel = lazy(
  () =>
    import(
      './components/AIAdvisorPanel'
    ),
)

const ArtifactsPanel = lazy(
  () =>
    import(
      './components/ArtifactsPanel'
    ),
)

type RunSummary = {
  run_id: string
  mission_id: string | null
  artifact_status: string
  updated_at_utc: string

  planned_distance_m: number | null
  actual_distance_m: number | null
  mission_duration_s: number | null
  flight_efficiency: number | null

  mean_rsrp_dbm: number | null
  min_rsrp_dbm: number | null

  mean_sinr_db: number | null
  min_sinr_db: number | null

  mean_coverage_score: number | null
  min_coverage_score: number | null

  incident_count: number
  advisor_count: number
  replan_decision_count: number
  replan_count: number
}

type Dashboard任务总览 = {
  runs_total: number
  complete_runs: number
  partial_runs: number
  latest_run: RunSummary | null
  latest_complete_run: RunSummary | null
}

function formatNumber(
  value: number | null | undefined,
  digits = 2,
) {
  if (value === null || value === undefined) {
    return '--'
  }

  return value.toFixed(digits)
}

function App() {
  const [overview, set任务总览] =
    useState<Dashboard任务总览 | null>(null)

  const [loading, setLoading] =
    useState(true)

  const [error, setError] =
    useState<string | null>(null)

  const [activeSection, setActiveSection] =
    useState('overview-section')


  function scrollToSection(
    sectionId: string,
  ) {
    setActiveSection(sectionId)

    document
      .getElementById(sectionId)
      ?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      })
  }


  useEffect(() => {
    async function load任务总览() {
      try {
        const response = await fetch(
          '/dashboard/overview',
        )

        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}`,
          )
        }

        const data =
          (await response.json()) as Dashboard任务总览

        set任务总览(data)
      } catch (err) {
        if (err instanceof Error) {
          setError(err.message)
        } else {
          setError('Unknown error')
        }
      } finally {
        setLoading(false)
      }
    }

    load任务总览()
  }, [])

  const run =
    overview?.latest_complete_run ?? null

  return (
    <div className="app-shell">

      <aside className="sidebar">

        <div className="brand">
          <div className="brand-logo">
            UAV
          </div>

          <div>
            <div className="brand-title">
              低空无人机
            </div>

            <div className="brand-subtitle">
              智能通信平台
            </div>
          </div>
        </div>

        <nav className="nav">

          <button
            type="button"
            className={
              `nav-item ${
                activeSection ===
                'overview-section'
                  ? 'active'
                  : ''
              }`
            }
            onClick={() =>
              scrollToSection(
                'overview-section',
              )
            }
          >
            任务总览
          </button>

          <button
            type="button"
            className={
              `nav-item ${
                activeSection ===
                'mission-section'
                  ? 'active'
                  : ''
              }`
            }
            onClick={() =>
              scrollToSection(
                'mission-section',
              )
            }
          >
            任务管理
          </button>

          <button
            type="button"
            className={
              `nav-item ${
                activeSection ===
                'communication-section'
                  ? 'active'
                  : ''
              }`
            }
            onClick={() =>
              scrollToSection(
                'communication-section',
              )
            }
          >
            通信监测
          </button>

          <button
            type="button"
            className={
              `nav-item ${
                activeSection ===
                'replanning-section'
                  ? 'active'
                  : ''
              }`
            }
            onClick={() =>
              scrollToSection(
                'replanning-section',
              )
            }
          >
            航迹重规划
          </button>

          <button
            type="button"
            className={
              `nav-item ${
                activeSection ===
                'advisor-section'
                  ? 'active'
                  : ''
              }`
            }
            onClick={() =>
              scrollToSection(
                'advisor-section',
              )
            }
          >
            AI 智能顾问
          </button>

          <button
            type="button"
            className={
              `nav-item ${
                activeSection ===
                'artifacts-section'
                  ? 'active'
                  : ''
              }`
            }
            onClick={() =>
              scrollToSection(
                'artifacts-section',
              )
            }
          >
            运行产物
          </button>

        </nav>

        <div className="sidebar-footer">
          V0.9 可视化平台
        </div>

      </aside>

      <main className="main-content">

        <header id="overview-section" className="topbar nav-section">

          <div>
            <h1>
              任务运行总览
            </h1>

            <p>
              UAV flight, 5G communication and
              intelligent replanning dashboard
            </p>
          </div>

          <div className="backend-status">
            <span className="status-dot" />

            后端已连接
          </div>

        </header>

        {loading && (
          <div className="message-card">
            正在加载平台数据...
          </div>
        )}

        {error && (
          <div className="message-card error">
            后端数据加载失败：
            {' '}
            {error}
          </div>
        )}

        {!loading && !error && overview && (
          <>

            <section id="mission-section" className="summary-strip nav-section">

              <div>
                <span>
                  运行总数
                </span>

                <strong>
                  {overview.runs_total}
                </strong>
              </div>

              <div>
                <span>
                  完整任务
                </span>

                <strong>
                  {overview.complete_runs}
                </strong>
              </div>

              <div>
                <span>
                  部分任务
                </span>

                <strong>
                  {overview.partial_runs}
                </strong>
              </div>

              <div className="summary-mission">
                <span>
                  当前展示任务
                </span>

                <strong>
                  {run?.mission_id ?? '--'}
                </strong>
              </div>

            </section>

            <section className="kpi-grid">

              <article className="kpi-card">
                <div className="kpi-label">
                  任务状态
                </div>

                <div className="kpi-value success">
                  {run?.artifact_status === 'COMPLETE' ? '已完成' : run?.artifact_status === 'PARTIAL' ? '部分完成' : run?.artifact_status ?? '--'}
                </div>

                <div className="kpi-note">
                  最新完整运行任务
                </div>
              </article>

              <article className="kpi-card">
                <div className="kpi-label">
                  飞行效率
                </div>

                <div className="kpi-value">
                  {run?.flight_efficiency != null
                    ? `${(
                        run.flight_efficiency * 100
                      ).toFixed(1)}%`
                    : '--'}
                </div>

                <div className="kpi-note">
                  规划航程与实际航程比值
                </div>
              </article>

              <article className="kpi-card">
                <div className="kpi-label">
                  平均 RSRP
                </div>

                <div className="kpi-value">
                  {formatNumber(
                    run?.mean_rsrp_dbm,
                    1,
                  )}

                  <small>
                    dBm
                  </small>
                </div>

                <div className="kpi-note">
                  最低值：
                  {' '}
                  {formatNumber(
                    run?.min_rsrp_dbm,
                    1,
                  )}
                  {' '}
                  dBm
                </div>
              </article>

              <article className="kpi-card">
                <div className="kpi-label">
                  平均 SINR
                </div>

                <div className="kpi-value">
                  {formatNumber(
                    run?.mean_sinr_db,
                    1,
                  )}

                  <small>
                    dB
                  </small>
                </div>

                <div className="kpi-note">
                  最低值：
                  {' '}
                  {formatNumber(
                    run?.min_sinr_db,
                    1,
                  )}
                  {' '}
                  dB
                </div>
              </article>

              <article className="kpi-card">
                <div className="kpi-label">
                  覆盖评分
                </div>

                <div className="kpi-value">
                  {formatNumber(
                    run?.mean_coverage_score,
                    3,
                  )}
                </div>

                <div className="kpi-note">
                  最低值：
                  {' '}
                  {formatNumber(
                    run?.min_coverage_score,
                    3,
                  )}
                </div>
              </article>

              <article className="kpi-card">
                <div className="kpi-label">
                  重规划次数
                </div>

                <div className="kpi-value">
                  {run?.replan_count ?? '--'}
                </div>

                <div className="kpi-note">
                  决策次数：
                  {' '}
                  {run?.replan_decision_count ?? '--'}
                </div>
              </article>

            </section>

            <section className="content-grid">

              <article className="panel">

                <div className="panel-header">
                  <h2>
                    任务概况
                  </h2>

                  <p>
                    最新完整任务
                  </p>
                </div>

                <div className="metric-row">
                  <span>
                    规划航程
                  </span>

                  <strong>
                    {formatNumber(
                      run?.planned_distance_m,
                    )}
                    {' '}
                    m
                  </strong>
                </div>

                <div className="metric-row">
                  <span>
                    实际航程
                  </span>

                  <strong>
                    {formatNumber(
                      run?.actual_distance_m,
                    )}
                    {' '}
                    m
                  </strong>
                </div>

                <div className="metric-row">
                  <span>
                    任务时长
                  </span>

                  <strong>
                    {formatNumber(
                      run?.mission_duration_s,
                    )}
                    {' '}
                    s
                  </strong>
                </div>

                <div className="metric-row">
                  <span>
                    异常事件记录
                  </span>

                  <strong>
                    {run?.incident_count ?? '--'}
                  </strong>
                </div>

              </article>

              <article className="panel">

                <div className="panel-header">
                  <h2>
                    通信质量概况
                  </h2>

                  <p>
                    5G运行时通信指标
                  </p>
                </div>

                <div className="communication-layout">

                  <div className="score-circle">
                    <strong>
                      {run?.mean_coverage_score != null
                        ? Math.round(
                            run.mean_coverage_score *
                            100,
                          )
                        : '--'}
                    </strong>

                    <span>
                      覆盖评分
                    </span>
                  </div>

                  <div className="communication-values">

                    <div>
                      <span>
                        平均 RSRP
                      </span>

                      <strong>
                        {formatNumber(
                          run?.mean_rsrp_dbm,
                          2,
                        )}
                        {' '}
                        dBm
                      </strong>
                    </div>

                    <div>
                      <span>
                        平均 SINR
                      </span>

                      <strong>
                        {formatNumber(
                          run?.mean_sinr_db,
                          2,
                        )}
                        {' '}
                        dB
                      </strong>
                    </div>

                  </div>

                </div>

              </article>

              <article id="replanning-section" className="panel large-panel nav-section">

                <div className="panel-header">
                  <h2>
                    无人机航迹与通信覆盖
                  </h2>

                  <p>
                    A3.2
                  </p>
                </div>

                <TrajectoryCoverage
                  runId={
                    run?.run_id ?? null
                  }
                />

              </article>

              <article className="panel large-panel">

                <div className="panel-header">
                  <h2>
                    异常与重规划时间线
                  </h2>

                  <p>
                    A3.3
                  </p>
                </div>

                <IncidentTimeline
                  runId={
                    run?.run_id ?? null
                  }
                />

              </article>

            </section>

            <div
              id="communication-section"
              className="nav-section"
            >
              <Suspense
                fallback={
                  <div className="lazy-panel">
                    正在加载通信质量时序监测...
                  </div>
                }
              >
                <CommunicationCharts
                  runId={
                    run?.run_id ?? null
                  }
                />
              </Suspense>
            </div>

            <div
              id="advisor-section"
              className="nav-section"
            >
              <Suspense
                fallback={
                  <div className="lazy-panel">
                    正在加载 AI / RAG 智能顾问...
                  </div>
                }
              >
                <AIAdvisorPanel
                  runId={
                    run?.run_id ?? null
                  }
                />
              </Suspense>
            </div>

            <div
              id="artifacts-section"
              className="nav-section"
            >
              <Suspense
                fallback={
                  <div className="lazy-panel">
                    正在加载运行产物...
                  </div>
                }
              >
                <ArtifactsPanel
                  runId={
                    run?.run_id ?? null
                  }
                />
              </Suspense>
            </div>

          </>
        )}

      </main>

    </div>
  )
}

export default App
