import {
  useEffect,
  useMemo,
  useState,
} from 'react'

import './ArtifactsPanel.css'


type Artifact = {
  name: string
  size_bytes: number
  modified_at_utc: string
}


type RunDetail = {
  run_id: string

  artifacts?: Artifact[]
}


type Props = {
  runId: string | null
}


function formatBytes(
  bytes: number,
) {
  if (bytes < 1024) {
    return `${bytes} B`
  }

  if (bytes < 1024 * 1024) {
    return `${(
      bytes / 1024
    ).toFixed(1)} KB`
  }

  return `${(
    bytes /
    1024 /
    1024
  ).toFixed(2)} MB`
}


function artifactType(
  name: string,
) {
  const extension =
    name
      .split('.')
      .pop()
      ?.toLowerCase()

  if (
    extension === 'png' ||
    extension === 'jpg' ||
    extension === 'jpeg'
  ) {
    return 'image'
  }

  if (extension === 'json') {
    return 'json'
  }

  if (extension === 'csv') {
    return 'csv'
  }

  return 'file'
}


function artifactLabel(
  type: string,
) {
  if (type === 'image') {
    return '图像'
  }

  if (type === 'json') {
    return 'JSON'
  }

  if (type === 'csv') {
    return 'CSV'
  }

  return '文件'
}


function ArtifactsPanel(
  {
    runId,
  }: Props,
) {
  const [data, setData] =
    useState<RunDetail | null>(
      null,
    )

  const [loading, setLoading] =
    useState(false)

  const [error, setError] =
    useState<string | null>(null)

  const [
    selectedImage,
    setSelectedImage,
  ] = useState<string | null>(
    null,
  )


  useEffect(() => {
    if (!runId) {
      return
    }

    async function loadArtifacts() {
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
            RunDetail

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

    loadArtifacts()
  }, [runId])


  const artifacts = useMemo(
    () =>
      data?.artifacts ?? [],
    [data],
  )


  const imageArtifacts =
    useMemo(
      () =>
        artifacts.filter(
          artifact =>
            artifactType(
              artifact.name,
            ) === 'image',
        ),
      [artifacts],
    )


  useEffect(() => {
    if (
      !selectedImage &&
      imageArtifacts.length > 0
    ) {
      setSelectedImage(
        imageArtifacts[0].name,
      )
    }
  }, [
    imageArtifacts,
    selectedImage,
  ])


  if (!runId) {
    return null
  }


  if (loading) {
    return (
      <section className="artifacts-panel">
        <div className="artifacts-message">
          正在加载运行产物...
        </div>
      </section>
    )
  }


  if (error) {
    return (
      <section className="artifacts-panel">
        <div className="artifacts-message artifacts-error">
          运行产物加载失败：
          {' '}
          {error}
        </div>
      </section>
    )
  }


  return (
    <section className="artifacts-panel">

      <div className="artifacts-header">

        <div>
          <h2>
            运行产物
          </h2>

          <p>
            任务执行生成的轨迹、通信、
            重规划与 AI 分析文件
          </p>
        </div>

        <div className="artifact-count">
          {artifacts.length}
          {' '}
          个文件
        </div>

      </div>


      <div className="artifacts-layout">

        <div className="artifact-list">

          {artifacts.map(
            artifact => {
              const type =
                artifactType(
                  artifact.name,
                )

              const artifactUrl =
                `/runs/${runId}/artifacts/${encodeURIComponent(
                  artifact.name,
                )}`

              const downloadUrl =
                `${artifactUrl}?download=true`

              return (
                <article
                  className="artifact-row"
                  key={artifact.name}
                >

                  <div
                    className={
                      `artifact-icon ${type}`
                    }
                  >
                    {type === 'image'
                      ? 'IMG'
                      : type.toUpperCase()}
                  </div>


                  <div className="artifact-info">

                    <strong>
                      {artifact.name}
                    </strong>

                    <div>
                      <span>
                        {artifactLabel(
                          type,
                        )}
                      </span>

                      <span>
                        {formatBytes(
                          artifact.size_bytes,
                        )}
                      </span>
                    </div>

                  </div>


                  <div className="artifact-actions">

                    {type === 'image' && (
                      <button
                        type="button"
                        onClick={() =>
                          setSelectedImage(
                            artifact.name,
                          )
                        }
                      >
                        预览
                      </button>
                    )}

                    {(type === 'json' ||
                      type === 'csv') && (
                      <a
                        href={artifactUrl}
                        target="_blank"
                        rel="noreferrer"
                      >
                        查看
                      </a>
                    )}

                    <a
                      className="download-action"
                      href={downloadUrl}
                    >
                      下载
                    </a>

                  </div>

                </article>
              )
            },
          )}

        </div>


        <div className="artifact-preview">

          <div className="artifact-preview-title">

            <strong>
              图像预览
            </strong>

            <span>
              {selectedImage ??
                '暂无图像'}
            </span>

          </div>


          {selectedImage ? (
            <div className="artifact-image-wrap">

              <img
                src={
                  `/runs/${runId}/artifacts/${encodeURIComponent(
                    selectedImage,
                  )}`
                }
                alt={selectedImage}
              />

            </div>
          ) : (
            <div className="artifact-preview-empty">
              当前任务没有可预览图像
            </div>
          )}


          {imageArtifacts.length > 1 && (
            <div className="artifact-image-tabs">

              {imageArtifacts.map(
                artifact => (
                  <button
                    type="button"
                    key={artifact.name}
                    className={
                      selectedImage ===
                      artifact.name
                        ? 'active'
                        : ''
                    }
                    onClick={() =>
                      setSelectedImage(
                        artifact.name,
                      )
                    }
                  >
                    {artifact.name}
                  </button>
                ),
              )}

            </div>
          )}

        </div>

      </div>

    </section>
  )
}


export default ArtifactsPanel
