import {
  useEffect,
  useMemo,
  useState,
} from 'react'

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import './CommunicationCharts.css'


type TrajectoryPoint = {
  elapsed_s: number | null
  rsrp_dbm: number | null
  sinr_db: number | null
  coverage_score: number | null
}


type TrajectoryResponse = {
  run_id: string
  total_points: number
  returned_points: number
  points: TrajectoryPoint[]
}


type IncidentEpisode = {
  episode_index: number

  incident: {
    elapsed_s: number | null
  }
}


type IncidentResponse = {
  episode_count: number
  episodes: IncidentEpisode[]
}


type Props = {
  runId: string | null
}


function formatTime(
  value: number,
) {
  return `${value.toFixed(0)} s`
}


function CommunicationCharts(
  {
    runId,
  }: Props,
) {
  const [trajectory, setTrajectory] =
    useState<TrajectoryResponse | null>(null)

  const [incidents, setIncidents] =
    useState<IncidentResponse | null>(null)

  const [loading, setLoading] =
    useState(false)

  const [error, setError] =
    useState<string | null>(null)


  useEffect(() => {
    if (!runId) {
      return
    }

    async function loadData() {
      try {
        setLoading(true)
        setError(null)

        const [
          trajectoryResponse,
          incidentResponse,
        ] = await Promise.all([
          fetch(
            `/runs/${runId}/trajectory?stride=1`,
          ),

          fetch(
            `/runs/${runId}/incidents`,
          ),
        ])

        if (!trajectoryResponse.ok) {
          throw new Error(
            `Trajectory HTTP ${trajectoryResponse.status}`,
          )
        }

        if (!incidentResponse.ok) {
          throw new Error(
            `Incidents HTTP ${incidentResponse.status}`,
          )
        }

        const trajectoryData =
          (await trajectoryResponse.json()) as
            TrajectoryResponse

        const incidentData =
          (await incidentResponse.json()) as
            IncidentResponse

        setTrajectory(
          trajectoryData,
        )

        setIncidents(
          incidentData,
        )
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

    loadData()
  }, [runId])


  const chartData = useMemo(
    () =>
      trajectory?.points.filter(
        (
          point,
        ): point is TrajectoryPoint & {
          elapsed_s: number
        } =>
          typeof point.elapsed_s ===
          'number',
      ) ?? [],
    [trajectory],
  )


  const incidentTimes = useMemo(
    () =>
      incidents?.episodes
        .map(
          episode => ({
            index:
              episode.episode_index,

            time:
              episode.incident
                .elapsed_s,
          }),
        )
        .filter(
          (
            item,
          ): item is {
            index: number
            time: number
          } =>
            typeof item.time ===
            'number',
        ) ?? [],
    [incidents],
  )


  if (!runId) {
    return null
  }


  if (loading) {
    return (
      <section className="comm-chart-panel">
        <div className="comm-chart-message">
          正在加载通信时序数据...
        </div>
      </section>
    )
  }


  if (error) {
    return (
      <section className="comm-chart-panel">
        <div className="comm-chart-message error">
          通信时序数据加载失败：
          {' '}
          {error}
        </div>
      </section>
    )
  }


  if (chartData.length === 0) {
    return (
      <section className="comm-chart-panel">
        <div className="comm-chart-message">
          暂无通信时序数据
        </div>
      </section>
    )
  }


  const incidentLines =
    incidentTimes.map(
      incident => (
        <ReferenceLine
          key={
            `incident-${incident.index}`
          }
          x={incident.time}
          stroke="#ef4444"
          strokeDasharray="4 4"
          strokeWidth={1.5}
        />
      ),
    )


  return (
    <section className="comm-chart-panel">

      <div className="comm-chart-header">

        <div>
          <h2>
            通信质量时序监测
          </h2>

          <p>
            基于飞行全过程通信采样数据
          </p>
        </div>

        <div className="comm-chart-meta">

          <span>
            {trajectory?.returned_points ?? 0}
            {' '}
            个采样点
          </span>

          {incidentTimes.map(
            incident => (
              <span
                className="incident-time-tag"
                key={incident.index}
              >
                异常
                {incident.index}
                ：
                {incident.time.toFixed(2)}
                {' '}
                s
              </span>
            ),
          )}

        </div>

      </div>


      <div className="comm-chart-grid">

        <article className="comm-chart-card">

          <div className="chart-title">
            <strong>
              RSRP 时序变化
            </strong>

            <span>
              dBm
            </span>
          </div>

          <div className="chart-area">
            <ResponsiveContainer
              width="100%"
              height="100%"
            >
              <LineChart
                data={chartData}
                margin={{
                  top: 10,
                  right: 10,
                  left: -10,
                  bottom: 0,
                }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#e8edf4"
                />

                <XAxis
                  dataKey="elapsed_s"
                  type="number"
                  domain={[
                    'dataMin',
                    'dataMax',
                  ]}
                  tickFormatter={formatTime}
                  tick={{
                    fontSize: 10,
                  }}
                />

                <YAxis
                  tick={{
                    fontSize: 10,
                  }}
                  width={46}
                />

                <Tooltip
                  labelFormatter={
                    value =>
                      `时间 ${Number(
                        value,
                      ).toFixed(2)} s`
                  }
                  formatter={
                    value => [
                      `${Number(
                        value,
                      ).toFixed(2)} dBm`,
                      'RSRP',
                    ]
                  }
                />

                {incidentLines}

                <Line
                  type="monotone"
                  dataKey="rsrp_dbm"
                  name="RSRP"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

        </article>


        <article className="comm-chart-card">

          <div className="chart-title">
            <strong>
              SINR 时序变化
            </strong>

            <span>
              dB
            </span>
          </div>

          <div className="chart-area">
            <ResponsiveContainer
              width="100%"
              height="100%"
            >
              <LineChart
                data={chartData}
                margin={{
                  top: 10,
                  right: 10,
                  left: -10,
                  bottom: 0,
                }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#e8edf4"
                />

                <XAxis
                  dataKey="elapsed_s"
                  type="number"
                  domain={[
                    'dataMin',
                    'dataMax',
                  ]}
                  tickFormatter={formatTime}
                  tick={{
                    fontSize: 10,
                  }}
                />

                <YAxis
                  tick={{
                    fontSize: 10,
                  }}
                  width={42}
                />

                <Tooltip
                  labelFormatter={
                    value =>
                      `时间 ${Number(
                        value,
                      ).toFixed(2)} s`
                  }
                  formatter={
                    value => [
                      `${Number(
                        value,
                      ).toFixed(2)} dB`,
                      'SINR',
                    ]
                  }
                />

                {incidentLines}

                <Line
                  type="monotone"
                  dataKey="sinr_db"
                  name="SINR"
                  stroke="#16a34a"
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

        </article>


        <article className="comm-chart-card">

          <div className="chart-title">
            <strong>
              覆盖评分时序变化
            </strong>

            <span>
              0–1
            </span>
          </div>

          <div className="chart-area">
            <ResponsiveContainer
              width="100%"
              height="100%"
            >
              <LineChart
                data={chartData}
                margin={{
                  top: 10,
                  right: 10,
                  left: -10,
                  bottom: 0,
                }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#e8edf4"
                />

                <XAxis
                  dataKey="elapsed_s"
                  type="number"
                  domain={[
                    'dataMin',
                    'dataMax',
                  ]}
                  tickFormatter={formatTime}
                  tick={{
                    fontSize: 10,
                  }}
                />

                <YAxis
                  domain={[0, 1]}
                  tick={{
                    fontSize: 10,
                  }}
                  width={38}
                />

                <Tooltip
                  labelFormatter={
                    value =>
                      `时间 ${Number(
                        value,
                      ).toFixed(2)} s`
                  }
                  formatter={
                    value => [
                      Number(
                        value,
                      ).toFixed(3),
                      '覆盖评分',
                    ]
                  }
                />

                {incidentLines}

                <Line
                  type="monotone"
                  dataKey="coverage_score"
                  name="覆盖评分"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

        </article>

      </div>


      <div className="comm-chart-footer">
        <span className="incident-line-example" />

        红色虚线表示通信异常触发时刻
      </div>

    </section>
  )
}


export default CommunicationCharts
