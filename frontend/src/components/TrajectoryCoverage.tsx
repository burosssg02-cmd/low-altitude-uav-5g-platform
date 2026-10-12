import {
  useEffect,
  useMemo,
  useState,
} from 'react'


type TrajectoryPoint = {
  elapsed_s: number | null
  east_m: number | null
  north_m: number | null
  altitude_m: number | null
  in_air: boolean | null
  serving_bs: string | null
  distance_m: number | null
  path_loss_db: number | null
  rsrp_dbm: number | null
  sinr_db: number | null
  coverage_score: number | null
  coverage_level: string | null
}


type TrajectoryResponse = {
  run_id: string
  source_artifact: string
  total_points: number
  returned_points: number
  stride: number
  points: TrajectoryPoint[]
}


type Props = {
  runId: string | null
}


const WIDTH = 900
const HEIGHT = 360
const PADDING = 44


function coverageColor(
  score: number | null,
) {
  if (score === null) {
    return '#94a3b8'
  }

  if (score >= 0.8) {
    return '#22c55e'
  }

  if (score >= 0.6) {
    return '#f59e0b'
  }

  return '#ef4444'
}


function formatValue(
  value: number | null,
  digits = 2,
) {
  if (value === null) {
    return '--'
  }

  return value.toFixed(digits)
}


export default function TrajectoryCoverage(
  {
    runId,
  }: Props,
) {
  const [data, setData] =
    useState<TrajectoryResponse | null>(
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

    async function loadTrajectory() {
      try {
        setLoading(true)
        setError(null)

        const response = await fetch(
          `/runs/${runId}/trajectory?stride=1`,
        )

        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}`,
          )
        }

        const result =
          (await response.json()) as
            TrajectoryResponse

        setData(result)
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Unknown trajectory error',
        )
      } finally {
        setLoading(false)
      }
    }

    loadTrajectory()
  }, [runId])


  const prepared = useMemo(() => {
    if (!data) {
      return null
    }

    const validPoints =
      data.points.filter(
        (
          point,
        ): point is TrajectoryPoint & {
          east_m: number
          north_m: number
        } =>
          typeof point.east_m === 'number' &&
          typeof point.north_m === 'number',
      )

    if (validPoints.length < 2) {
      return null
    }

    const eastValues =
      validPoints.map(
        point => point.east_m,
      )

    const northValues =
      validPoints.map(
        point => point.north_m,
      )

    const minEast =
      Math.min(...eastValues)

    const maxEast =
      Math.max(...eastValues)

    const minNorth =
      Math.min(...northValues)

    const maxNorth =
      Math.max(...northValues)

    const eastRange =
      Math.max(
        maxEast - minEast,
        1,
      )

    const northRange =
      Math.max(
        maxNorth - minNorth,
        1,
      )

    const innerWidth =
      WIDTH - PADDING * 2

    const innerHeight =
      HEIGHT - PADDING * 2

    const scale = Math.min(
      innerWidth / eastRange,
      innerHeight / northRange,
    )

    const usedWidth =
      eastRange * scale

    const usedHeight =
      northRange * scale

    const offsetX =
      PADDING +
      (innerWidth - usedWidth) / 2

    const offsetY =
      PADDING +
      (innerHeight - usedHeight) / 2

    const mapped =
      validPoints.map(point => ({
        ...point,

        x:
          offsetX +
          (point.east_m - minEast) *
            scale,

        y:
          HEIGHT -
          (
            offsetY +
            (point.north_m - minNorth) *
              scale
          ),
      }))

    const coverageValues =
      validPoints
        .map(
          point =>
            point.coverage_score,
        )
        .filter(
          (
            value,
          ): value is number =>
            typeof value === 'number',
        )

    const rsrpValues =
      validPoints
        .map(
          point => point.rsrp_dbm,
        )
        .filter(
          (
            value,
          ): value is number =>
            typeof value === 'number',
        )

    const sinrValues =
      validPoints
        .map(
          point => point.sinr_db,
        )
        .filter(
          (
            value,
          ): value is number =>
            typeof value === 'number',
        )

    return {
      points: mapped,

      minEast,
      maxEast,
      minNorth,
      maxNorth,

      minCoverage:
        coverageValues.length
          ? Math.min(
              ...coverageValues,
            )
          : null,

      minRsrp:
        rsrpValues.length
          ? Math.min(
              ...rsrpValues,
            )
          : null,

      minSinr:
        sinrValues.length
          ? Math.min(
              ...sinrValues,
            )
          : null,
    }
  }, [data])


  if (!runId) {
    return (
      <div className="trajectory-empty">
        未选择任务
      </div>
    )
  }


  if (loading) {
    return (
      <div className="trajectory-empty">
        正在加载航迹数据...
      </div>
    )
  }


  if (error) {
    return (
      <div className="trajectory-empty trajectory-error">
        航迹数据加载失败：
        {' '}
        {error}
      </div>
    )
  }


  if (!data || !prepared) {
    return (
      <div className="trajectory-empty">
        暂无航迹数据
      </div>
    )
  }


  const start =
    prepared.points[0]

  const end =
    prepared.points[
      prepared.points.length - 1
    ]


  return (
    <div className="trajectory-shell">

      <div className="trajectory-toolbar">

        <div className="trajectory-legend">

          <div className="legend-item">
            <span
              className="legend-swatch good"
            />
            良好 ≥ 0.80
          </div>

          <div className="legend-item">
            <span
              className="legend-swatch fair"
            />
            一般 0.60–0.80
          </div>

          <div className="legend-item">
            <span
              className="legend-swatch poor"
            />
            Poor &lt; 0.60
          </div>

        </div>

        <div className="trajectory-sample-count">
          {data.returned_points}
          {' '}
          个采样点
        </div>

      </div>


      <div className="trajectory-canvas">

        <svg
          className="trajectory-svg"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label="UAV communication trajectory"
        >

          <defs>
            <pattern
              id="trajectory-grid"
              width="45"
              height="45"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M 45 0 L 0 0 0 45"
                fill="none"
                stroke="#e7edf5"
                strokeWidth="1"
              />
            </pattern>
          </defs>

          <rect
            x="0"
            y="0"
            width={WIDTH}
            height={HEIGHT}
            fill="url(#trajectory-grid)"
          />


          {prepared.points
            .slice(0, -1)
            .map(
              (
                point,
                index,
              ) => {
                const next =
                  prepared.points[
                    index + 1
                  ]

                return (
                  <line
                    key={`segment-${index}`}
                    x1={point.x}
                    y1={point.y}
                    x2={next.x}
                    y2={next.y}
                    stroke={coverageColor(
                      next.coverage_score ??
                        point.coverage_score,
                    )}
                    strokeWidth="5"
                    strokeLinecap="round"
                  />
                )
              },
            )}


          {prepared.points.map(
            (
              point,
              index,
            ) => {
              if (
                point.coverage_score ===
                  null ||
                point.coverage_score >=
                  0.6
              ) {
                return null
              }

              return (
                <circle
                  key={`poor-${index}`}
                  cx={point.x}
                  cy={point.y}
                  r="5.5"
                  fill="#ef4444"
                  stroke="white"
                  strokeWidth="2"
                />
              )
            },
          )}


          <circle
            cx={start.x}
            cy={start.y}
            r="8"
            fill="#2563eb"
            stroke="white"
            strokeWidth="3"
          />

          <text
            x={start.x + 11}
            y={start.y - 10}
            className="trajectory-svg-label"
          >
            起点
          </text>


          <circle
            cx={end.x}
            cy={end.y}
            r="8"
            fill="#111827"
            stroke="white"
            strokeWidth="3"
          />

          <text
            x={end.x + 11}
            y={end.y - 10}
            className="trajectory-svg-label"
          >
            终点
          </text>


          <text
            x={WIDTH / 2}
            y={HEIGHT - 8}
            textAnchor="middle"
            className="trajectory-axis-label"
          >
            东向位移 (m)
          </text>

          <text
            x="14"
            y={HEIGHT / 2}
            textAnchor="middle"
            transform={
              `rotate(-90 14 ${HEIGHT / 2})`
            }
            className="trajectory-axis-label"
          >
            北向位移 (m)
          </text>

        </svg>

      </div>


      <div className="trajectory-stats">

        <div className="trajectory-stat">
          <span>
            东向跨度
          </span>

          <strong>
            {formatValue(
              prepared.maxEast -
                prepared.minEast,
              1,
            )}
            {' '}
            m
          </strong>
        </div>

        <div className="trajectory-stat">
          <span>
            北向跨度
          </span>

          <strong>
            {formatValue(
              prepared.maxNorth -
                prepared.minNorth,
              1,
            )}
            {' '}
            m
          </strong>
        </div>

        <div className="trajectory-stat">
          <span>
            最低覆盖评分
          </span>

          <strong>
            {formatValue(
              prepared.minCoverage,
              3,
            )}
          </strong>
        </div>

        <div className="trajectory-stat">
          <span>
            最低 RSRP
          </span>

          <strong>
            {formatValue(
              prepared.minRsrp,
              1,
            )}
            {' '}
            dBm
          </strong>
        </div>

        <div className="trajectory-stat">
          <span>
            最低 SINR
          </span>

          <strong>
            {formatValue(
              prepared.minSinr,
              1,
            )}
            {' '}
            dB
          </strong>
        </div>

      </div>

    </div>
  )
}
