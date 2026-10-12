import {
  useEffect,
  useState,
} from 'react'


type Episode = {
  episode_index: number

  incident: {
    elapsed_s: number | null
    rsrp_dbm: number | null
    sinr_db: number | null
    coverage_score: number | null
  }

  decision: {
    decision: string | null
    selected_planner: string | null
    latency_ms: number | null
  }

  route_application: {
    incident_to_route_apply_s: number | null
    waypoint_count: number | null
  }

  recovery: {
    recovery_time_s: number | null
    recovery_path_m: number | null
  }

  communication_change: {
    rsrp_improvement_db: number | null
    sinr_improvement_db: number | null
    coverage_score_improvement: number | null
  }

  advisor: {
    status: string | null
    error_type: string | null
  }
}


type IncidentResponse = {
  run_id: string
  mission_status: string | null
  episode_count: number
  episodes: Episode[]
}


type Props = {
  runId: string | null
}


function num(
  value: number | null,
  digits = 2,
) {
  if (value === null) {
    return '--'
  }

  return value.toFixed(digits)
}


export default function IncidentTimeline(
  {
    runId,
  }: Props,
) {
  const [data, setData] =
    useState<IncidentResponse | null>(null)

  const [loading, setLoading] =
    useState(false)

  const [error, setError] =
    useState<string | null>(null)


  useEffect(() => {
    if (!runId) {
      return
    }

    async function loadIncidents() {
      try {
        setLoading(true)
        setError(null)

        const response = await fetch(
          `/runs/${runId}/incidents`,
        )

        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}`,
          )
        }

        const result =
          (await response.json()) as
            IncidentResponse

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

    loadIncidents()
  }, [runId])


  if (loading) {
    return (
      <div className="incident-empty">
        正在加载异常事件...
      </div>
    )
  }


  if (error) {
    return (
      <div className="incident-empty incident-error">
        异常数据加载失败：{error}
      </div>
    )
  }


  if (
    !data ||
    data.episodes.length === 0
  ) {
    return (
      <div className="incident-empty">
        当前任务没有重规划事件
      </div>
    )
  }


  return (
    <div className="incident-list">

      {data.episodes.map(
        episode => (
          <article
            className="incident-episode"
            key={episode.episode_index}
          >

            <div className="incident-title-row">

              <div>
                <span className="episode-badge">
                  Episode {episode.episode_index}
                </span>

                <strong>
                  第 {episode.episode_index} 次通信异常与重规划
                </strong>
              </div>

              <span className="replan-badge">
                已重规划
              </span>

            </div>


            <div className="timeline-flow">

              <div className="timeline-step danger">

                <div className="timeline-dot" />

                <div>
                  <strong>
                    通信异常
                  </strong>

                  <span>
                    {num(
                      episode.incident.elapsed_s,
                      2,
                    )}
                    {' '}
                    s
                  </span>

                  <p>
                    RSRP：
                    {num(
                      episode.incident.rsrp_dbm,
                      2,
                    )}
                    {' '}
                    dBm
                  </p>

                  <p>
                    覆盖评分：
                    {num(
                      episode.incident.coverage_score,
                      3,
                    )}
                  </p>
                </div>

              </div>


              <div className="timeline-arrow">
                →
              </div>


              <div className="timeline-step decision">

                <div className="timeline-dot" />

                <div>
                  <strong>
                    Fast Policy 决策
                  </strong>

                  <span>
                    {num(
                      episode.decision.latency_ms,
                      3,
                    )}
                    {' '}
                    ms
                  </span>

                  <p>
                    建议通信感知航迹重规划
                  </p>

                  <p>
                    {episode.decision.selected_planner
                      ?? '--'}
                  </p>
                </div>

              </div>


              <div className="timeline-arrow">
                →
              </div>


              <div className="timeline-step route">

                <div className="timeline-dot" />

                <div>
                  <strong>
                    新航迹应用
                  </strong>

                  <span>
                    {num(
                      episode.route_application
                        .incident_to_route_apply_s,
                      4,
                    )}
                    {' '}
                    s
                  </span>

                  <p>
                    航点数：
                    {episode.route_application
                      .waypoint_count ?? '--'}
                  </p>
                </div>

              </div>


              <div className="timeline-arrow">
                →
              </div>


              <div className="timeline-step recovery">

                <div className="timeline-dot" />

                <div>
                  <strong>
                    通信恢复
                  </strong>

                  <span>
                    {num(
                      episode.recovery
                        .recovery_time_s,
                      2,
                    )}
                    {' '}
                    s
                  </span>

                  <p>
                    RSRP 改善：
                    +
                    {num(
                      episode.communication_change
                        .rsrp_improvement_db,
                      2,
                    )}
                    {' '}
                    dB
                  </p>

                  <p>
                    覆盖评分提升：
                    +
                    {num(
                      episode.communication_change
                        .coverage_score_improvement,
                      3,
                    )}
                  </p>
                </div>

              </div>

            </div>


            <div className="advisor-strip">

              <span>
                AI Advisor
              </span>

              <strong
                className={
                  episode.advisor.status ===
                    'ADVISOR_FAILED'
                    ? 'advisor-failed'
                    : 'advisor-ok'
                }
              >
                {episode.advisor.status ===
                  'ADVISOR_FAILED'
                  ? '超时 / 失败'
                  : episode.advisor.status ??
                    '--'}
              </strong>

              {episode.advisor.error_type && (
                <small>
                  {episode.advisor.error_type}
                </small>
              )}

            </div>

          </article>
        ),
      )}

    </div>
  )
}
