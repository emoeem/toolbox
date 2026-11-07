#pragma once

#include <QImage>
#include <QMutex>
#include <QPointF>
#include <QQuickItem>
#include <QUrl>
#include <QtQml/qqml.h>

namespace toolbox {

// Minimal GPU image viewport (Phase 2 prototype).
//
// Renders the decoded image through the Qt Quick Scene Graph
// (QSGSimpleTextureNode). Zoom/pan are computed in item coordinates; the
// texture itself is uploaded only inside updatePaintNode (render thread).
//
// Phase 2 scope: local file display, wheel zoom (cursor anchored), drag pan,
// fit / 100%, checkerboard for alpha images. Phase 3+ will feed this canvas
// from the Python Worker (preview files) instead of local QImageReader.
class ImageCanvas : public QQuickItem {
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(QUrl source READ source WRITE setSource NOTIFY sourceChanged)
    Q_PROPERTY(qreal zoom READ zoom WRITE setZoom NOTIFY zoomChanged)
    Q_PROPERTY(QSize imageSize READ imageSize NOTIFY imageSizeChanged)
    Q_PROPERTY(bool showCheckerboard READ showCheckerboard WRITE setShowCheckerboard NOTIFY
                   showCheckerboardChanged)
    Q_PROPERTY(QPointF mousePosition READ mousePosition NOTIFY mousePositionChanged)
    Q_PROPERTY(bool busy READ busy NOTIFY busyChanged)

  public:
    explicit ImageCanvas(QQuickItem *parent = nullptr);

    QUrl source() const { return m_source; }
    void setSource(const QUrl &source);

    qreal zoom() const { return m_zoom; }
    void setZoom(qreal zoom);

    QSize imageSize() const { return m_imageSize; }
    bool showCheckerboard() const { return m_showCheckerboard; }
    void setShowCheckerboard(bool show);
    QPointF mousePosition() const { return m_mousePosition; }
    bool busy() const { return m_busy; }

    Q_INVOKABLE void fitToWindow();
    Q_INVOKABLE void setActualSize();
    Q_INVOKABLE void zoomBy(qreal factor); // anchored to the item center

  signals:
    void sourceChanged();
    void zoomChanged();
    void imageSizeChanged();
    void showCheckerboardChanged();
    void mousePositionChanged();
    void busyChanged();
    void imageDropped(const QUrl &url);
    void loadFailed(const QString &reason);

  protected:
    QSGNode *updatePaintNode(QSGNode *oldNode, UpdatePaintNodeData *data) override;
    void geometryChange(const QRectF &newGeometry, const QRectF &oldGeometry) override;
    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void mouseReleaseEvent(QMouseEvent *event) override;
    void mouseDoubleClickEvent(QMouseEvent *event) override;
    void hoverMoveEvent(QHoverEvent *event) override;
    void wheelEvent(QWheelEvent *event) override;
    void dragEnterEvent(QDragEnterEvent *event) override;
    void dropEvent(QDropEvent *event) override;

  private:
    QRectF imageRect() const;
    QPointF mapToImage(const QPointF &itemPos) const;
    void emitMousePosition(const QPointF &itemPos);

    QUrl m_source;
    QSize m_imageSize;
    qreal m_zoom = 1.0;
    QPointF m_panOffset; // image rect top-left in item coordinates
    bool m_showCheckerboard = true;
    QPointF m_mousePosition;
    bool m_busy = false;
    bool m_dragging = false;
    QPointF m_lastDragPos;

    // Render-thread image state, guarded by m_mutex. m_pendingImage is
    // written on the GUI thread; updatePaintNode swaps it into m_renderImage.
    QMutex m_mutex;
    QImage m_pendingImage;
    QImage m_renderImage;
    bool m_hasPending = false;
};

} // namespace toolbox
