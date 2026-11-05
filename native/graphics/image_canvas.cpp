#include "image_canvas.h"

#include <QDragEnterEvent>
#include <QDropEvent>
#include <QHoverEvent>
#include <QImageReader>
#include <QMimeData>
#include <QMouseEvent>
#include <QPainter>
#include <QQuickWindow>
#include <QWheelEvent>
#include <QtGlobal>

#include <QSGSimpleTextureNode>

namespace toolbox {
namespace {

constexpr qreal kMinZoom = 0.01;
constexpr qreal kMaxZoom = 32.0;
constexpr int kCheckerCell = 8; // image pixels per checker cell

// Checkerboard composited in image space: it represents pixel transparency,
// so it must not scale differently from the image content.
QImage compositeCheckerboard(const QImage &image)
{
    QImage canvas = image.convertToFormat(QImage::Format_ARGB32_Premultiplied);
    QPainter painter(&canvas);
    painter.setCompositionMode(QPainter::CompositionMode_SourceOver);
    const int w = canvas.width();
    const int h = canvas.height();
    for (int y = 0; y < h; y += kCheckerCell) {
        for (int x = 0; x < w; x += kCheckerCell) {
            const bool dark = ((x / kCheckerCell) + (y / kCheckerCell)) % 2 == 0;
            painter.fillRect(x, y, kCheckerCell, kCheckerCell,
                             dark ? QColor(0x2a, 0x2d, 0x42) : QColor(0x3a, 0x3d, 0x52));
        }
    }
    painter.end();
    return canvas;
}

} // namespace

ImageCanvas::ImageCanvas(QQuickItem *parent)
    : QQuickItem(parent)
{
    setFlag(ItemAcceptsDrops, true);
    setAcceptedMouseButtons(Qt::LeftButton);
    setAcceptHoverEvents(true);
}

void ImageCanvas::setSource(const QUrl &source)
{
    if (m_source == source)
        return;
    m_source = source;
    emit sourceChanged();

    const QString path = source.isLocalFile() ? source.toLocalFile() : source.toString();
    m_busy = true;
    emit busyChanged();

    QImageReader reader(path);
    reader.setAutoTransform(true);
    QImage decoded;
    if (!reader.read(&decoded) || decoded.isNull()) {
        m_busy = false;
        emit busyChanged();
        emit loadFailed(reader.errorString());
        return;
    }

    {
        QMutexLocker locker(&m_mutex);
        m_imageSize = decoded.size();
        m_pendingImage = (decoded.hasAlphaChannel() && m_showCheckerboard)
                             ? compositeCheckerboard(decoded)
                             : std::move(decoded);
        m_hasPending = true;
    }
    emit imageSizeChanged();

    m_busy = false;
    emit busyChanged();
    fitToWindow();
    update();
}

void ImageCanvas::setZoom(qreal zoom)
{
    const qreal clamped = qBound(kMinZoom, zoom, kMaxZoom);
    if (qFuzzyCompare(clamped, m_zoom))
        return;
    m_zoom = clamped;
    emit zoomChanged();
    update();
}

void ImageCanvas::setShowCheckerboard(bool show)
{
    if (m_showCheckerboard == show)
        return;
    m_showCheckerboard = show;
    emit showCheckerboardChanged();
    // Recomposite with/without the checker pattern.
    if (m_source.isValid())
        setSource(m_source);
}

void ImageCanvas::fitToWindow()
{
    const QSize size = m_imageSize;
    if (size.isEmpty() || width() <= 0 || height() <= 0)
        return;
    const qreal fit = qMin(width() / qreal(size.width()),
                           height() / qreal(size.height()));
    m_panOffset = QPointF((width() - size.width() * fit) / 2.0,
                          (height() - size.height() * fit) / 2.0);
    setZoom(fit);
}

void ImageCanvas::setActualSize()
{
    m_panOffset = QPointF((width() - m_imageSize.width()) / 2.0,
                          (height() - m_imageSize.height()) / 2.0);
    setZoom(1.0);
}

void ImageCanvas::zoomBy(qreal factor)
{
    if (m_imageSize.isEmpty())
        return;
    const QPointF center(width() / 2.0, height() / 2.0);
    const QPointF imagePoint = mapToImage(center);
    setZoom(m_zoom * factor);
    m_panOffset = center - imagePoint * m_zoom;
    update();
}

QRectF ImageCanvas::imageRect() const
{
    return QRectF(m_panOffset.x(), m_panOffset.y(),
                  qreal(m_imageSize.width()) * m_zoom,
                  qreal(m_imageSize.height()) * m_zoom);
}

QPointF ImageCanvas::mapToImage(const QPointF &itemPos) const
{
    if (m_imageSize.isEmpty() || m_zoom <= 0)
        return QPointF(-1, -1);
    return QPointF((itemPos.x() - m_panOffset.x()) / m_zoom,
                   (itemPos.y() - m_panOffset.y()) / m_zoom);
}

void ImageCanvas::emitMousePosition(const QPointF &itemPos)
{
    const QPointF imagePos = mapToImage(itemPos);
    if (imagePos == m_mousePosition)
        return;
    m_mousePosition = imagePos;
    emit mousePositionChanged();
}

QSGNode *ImageCanvas::updatePaintNode(QSGNode *oldNode, UpdatePaintNodeData *data)
{
    Q_UNUSED(data);
    auto *node = static_cast<QSGSimpleTextureNode *>(oldNode);
    if (!node) {
        node = new QSGSimpleTextureNode;
        node->setOwnsTexture(true);
    }

    {
        QMutexLocker locker(&m_mutex);
        if (m_hasPending) {
            m_renderImage = std::move(m_pendingImage);
            m_pendingImage = QImage();
            m_hasPending = false;
        }
    }

    if (!m_renderImage.isNull()) {
        // createTextureFromImage must run with the render context current,
        // which updatePaintNode guarantees. setOwnsTexture(true) makes the
        // node delete the previous texture when a new one is assigned.
        QSGTexture *texture = window()->createTextureFromImage(m_renderImage);
        node->setTexture(texture);
        node->setRect(imageRect());
        node->setFiltering(m_zoom < 1.0 ? QSGTexture::Linear : QSGTexture::Nearest);
    } else {
        node->setRect(QRectF());
    }

    node->markDirty(QSGNode::DirtyGeometry | QSGNode::DirtyMaterial);
    return node;
}

void ImageCanvas::geometryChange(const QRectF &newGeometry, const QRectF &oldGeometry)
{
    QQuickItem::geometryChange(newGeometry, oldGeometry);
    if (newGeometry.size() != oldGeometry.size())
        fitToWindow();
}

void ImageCanvas::mousePressEvent(QMouseEvent *event)
{
    m_dragging = true;
    m_lastDragPos = event->position();
    event->accept();
}

void ImageCanvas::mouseMoveEvent(QMouseEvent *event)
{
    if (m_dragging) {
        const QPointF delta = event->position() - m_lastDragPos;
        m_lastDragPos = event->position();
        m_panOffset += delta;
        update();
    }
    emitMousePosition(event->position());
    event->accept();
}

void ImageCanvas::mouseReleaseEvent(QMouseEvent *event)
{
    m_dragging = false;
    event->accept();
}

void ImageCanvas::mouseDoubleClickEvent(QMouseEvent *event)
{
    fitToWindow();
    event->accept();
}

void ImageCanvas::hoverMoveEvent(QHoverEvent *event)
{
    emitMousePosition(event->position());
    event->accept();
}

void ImageCanvas::wheelEvent(QWheelEvent *event)
{
    const qreal delta = event->angleDelta().y();
    if (delta == 0 || m_imageSize.isEmpty())
        return;

    const QPointF cursor = event->position();
    const QPointF imagePoint = mapToImage(cursor);
    const qreal factor = std::pow(qreal(1.0015), delta);
    setZoom(m_zoom * factor);
    // Keep the image point under the cursor anchored while zooming.
    m_panOffset = cursor - imagePoint * m_zoom;
    update();
    event->accept();
}

void ImageCanvas::dragEnterEvent(QDragEnterEvent *event)
{
    if (event->mimeData()->hasUrls()) {
        event->acceptProposedAction();
        return;
    }
    event->ignore();
}

void ImageCanvas::dropEvent(QDropEvent *event)
{
    const auto urls = event->mimeData()->urls();
    if (urls.isEmpty())
        return;
    event->acceptProposedAction();
    emit imageDropped(urls.first());
}

} // namespace toolbox
