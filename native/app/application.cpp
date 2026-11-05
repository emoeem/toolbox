#include "application.h"

#include <QQmlEngine>
#include <QJSEngine>
#include <qglobal.h>

namespace toolbox {

Application::Application(QObject *parent)
    : QObject(parent)
{
    buildCatalog();
    // Phase 2 default landing page; HomePage becomes the entry once it has
    // real content in Phase 4.
    setCurrentPage(QUrl(QStringLiteral("qrc:/Toolbox/ui/pages/HomePage.qml")));
}

Application *Application::create(QQmlEngine *qmlEngine, QJSEngine *jsEngine)
{
    // The instance must outlive the engine bindings; ownership stays with QML.
    auto *instance = new Application();
    Q_UNUSED(qmlEngine);
    Q_UNUSED(jsEngine);
    return instance;
}

QString Application::qtVersion() const
{
    return QString::fromLatin1(qVersion());
}

void Application::setCurrentPage(const QUrl &page)
{
    if (m_currentPage == page)
        return;
    m_currentPage = page;
    emit currentPageChanged();
}

void Application::navigate(const QString &pageId)
{
    const auto page = m_navModel.pageForId(pageId);
    if (!page.isEmpty())
        setCurrentPage(page);
}

void Application::buildCatalog()
{
    // Navigation entries. P2 destinations (analyze/ai/files) are real pages
    // only in later phases; until then they render the honest "planned" page.
    m_navModel.addEntry({QStringLiteral("home"),
                         QStringLiteral("首页"),
                         QStringLiteral("qrc:/Toolbox/ui/pages/HomePage.qml"),
                         true,
                         QStringLiteral("P0")});
    m_navModel.addEntry({QStringLiteral("editor"),
                         QStringLiteral("编辑"),
                         QStringLiteral("qrc:/Toolbox/ui/pages/EditorPage.qml"),
                         true,
                         QStringLiteral("P0")});
    m_navModel.addEntry({QStringLiteral("create"),
                         QStringLiteral("创作"),
                         QStringLiteral("qrc:/Toolbox/ui/pages/FractalPage.qml"),
                         true,
                         QStringLiteral("P1")});
    m_navModel.addEntry({QStringLiteral("batch"),
                         QStringLiteral("批量"),
                         QStringLiteral("qrc:/Toolbox/ui/pages/BatchPage.qml"),
                         true,
                         QStringLiteral("P1")});
    m_navModel.addEntry({QStringLiteral("analyze"),
                         QStringLiteral("分析"),
                         QStringLiteral("qrc:/Toolbox/ui/pages/PlannedPage.qml"),
                         false,
                         QStringLiteral("P2")});
    m_navModel.addEntry({QStringLiteral("ai"),
                         QStringLiteral("AI"),
                         QStringLiteral("qrc:/Toolbox/ui/pages/PlannedPage.qml"),
                         false,
                         QStringLiteral("P2")});
    m_navModel.addEntry({QStringLiteral("files"),
                         QStringLiteral("文件工具"),
                         QStringLiteral("qrc:/Toolbox/ui/pages/PlannedPage.qml"),
                         false,
                         QStringLiteral("P2")});
    m_navModel.addEntry({QStringLiteral("settings"),
                         QStringLiteral("设置"),
                         QStringLiteral("qrc:/Toolbox/ui/pages/SettingsPage.qml"),
                         true,
                         QStringLiteral("P0")});

    // Tool catalog (Phase 2 subset, mirrored from docs/ui-migration-matrix.md).
    // "available" reflects the migration matrix phase, not a UI presence.
    using E = ToolModel::Entry;
    m_toolModel.addEntry({E{QStringLiteral("tool.open-image"), QStringLiteral("打开图像"),
                            QStringLiteral("图像编辑"), true, QStringLiteral("P0"),
                            QStringLiteral("open file 打开")}});
    m_toolModel.addEntry({E{QStringLiteral("tool.adjust"), QStringLiteral("调整"),
                            QStringLiteral("图像编辑"), true, QStringLiteral("P0"),
                            QStringLiteral("亮度 对比度 饱和度 曝光 色相")}});
    m_toolModel.addEntry({E{QStringLiteral("tool.filter"), QStringLiteral("滤镜"),
                            QStringLiteral("图像编辑"), true, QStringLiteral("P0"),
                            QStringLiteral("滤镜 滤镜链 预设")}});
    m_toolModel.addEntry({E{QStringLiteral("tool.crop"), QStringLiteral("裁剪"),
                            QStringLiteral("图像编辑"), true, QStringLiteral("P0"),
                            QStringLiteral("裁剪 比例")}});
    m_toolModel.addEntry({E{QStringLiteral("tool.transform"), QStringLiteral("变换"),
                            QStringLiteral("图像编辑"), true, QStringLiteral("P0"),
                            QStringLiteral("旋转 翻转 缩放")}});
    m_toolModel.addEntry({E{QStringLiteral("tool.fractal"), QStringLiteral("分形生成器"),
                            QStringLiteral("创作"), true, QStringLiteral("P1"),
                            QStringLiteral("fractal mandelbrot julia")}});
    m_toolModel.addEntry({E{QStringLiteral("tool.texture"), QStringLiteral("纹理生成器"),
                            QStringLiteral("创作"), true, QStringLiteral("P1"),
                            QStringLiteral("texture noise 纹理")}});
    m_toolModel.addEntry({E{QStringLiteral("tool.shader"), QStringLiteral("Shader Studio"),
                            QStringLiteral("创作"), true, QStringLiteral("P1"),
                            QStringLiteral("glsl shader")}});
    m_toolModel.addEntry({E{QStringLiteral("tool.gmic"), QStringLiteral("G'MIC 滤镜"),
                            QStringLiteral("滤镜效果"), false, QStringLiteral("P1"),
                            QStringLiteral("gmic")}});
    m_toolModel.addEntry({E{QStringLiteral("tool.batch"), QStringLiteral("批量处理"),
                            QStringLiteral("批量工具"), true, QStringLiteral("P1"),
                            QStringLiteral("batch 批量")}});
    m_toolModel.addEntry({E{QStringLiteral("tool.ocr"), QStringLiteral("OCR"),
                            QStringLiteral("文件工具"), false, QStringLiteral("P2"),
                            QStringLiteral("ocr tesseract 文字识别")}});
    m_toolModel.addEntry({E{QStringLiteral("tool.remove-bg"), QStringLiteral("AI 抠图"),
                            QStringLiteral("AI 工具"), false, QStringLiteral("P2"),
                            QStringLiteral("ai rembg 抠图 背景移除")}});
}

} // namespace toolbox
