/****************************************************************************
** Generated QML type registration code
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <QtQml/qqml.h>
#include <QtQml/qqmlmoduleregistration.h>

#if __has_include(<Def.h>)
#  include <Def.h>
#endif
#if __has_include(<FluApp.h>)
#  include <FluApp.h>
#endif
#if __has_include(<FluColors.h>)
#  include <FluColors.h>
#endif
#if __has_include(<FluTextStyle.h>)
#  include <FluTextStyle.h>
#endif
#if __has_include(<FluTheme.h>)
#  include <FluTheme.h>
#endif
#if __has_include(<FluTools.h>)
#  include <FluTools.h>
#endif
#if __has_include(<WindowHelper.h>)
#  include <WindowHelper.h>
#endif


#if !defined(QT_STATIC)
#define Q_QMLTYPE_EXPORT Q_DECL_EXPORT
#else
#define Q_QMLTYPE_EXPORT
#endif
Q_QMLTYPE_EXPORT void qml_register_types_FluentUI()
{
    QT_WARNING_PUSH QT_WARNING_DISABLE_DEPRECATED
    qmlRegisterTypesAndRevisions<FluApp>("FluentUI", 1);
    qmlRegisterTypesAndRevisions<FluColors>("FluentUI", 1);
    qmlRegisterTypesAndRevisions<FluTextStyle>("FluentUI", 1);
    qmlRegisterTypesAndRevisions<FluTheme>("FluentUI", 1);
    qmlRegisterTypesAndRevisions<FluTools>("FluentUI", 1);
    {
        Q_CONSTINIT static auto metaType = QQmlPrivate::metaTypeForNamespace(
            [](const QtPrivate::QMetaTypeInterface *) {return &Fluent_Awesome::staticMetaObject;},
            "Fluent_Awesome");
        QMetaType(&metaType).id();
    }
    qmlRegisterNamespaceAndRevisions(&Fluent_Awesome::staticMetaObject, "FluentUI", 1, nullptr, &Fluent_Awesome::staticMetaObject, nullptr);
    qmlRegisterEnum<Fluent_Awesome::Fluent_AwesomeType>("Fluent_Awesome::Fluent_AwesomeType");
    {
        Q_CONSTINIT static auto metaType = QQmlPrivate::metaTypeForNamespace(
            [](const QtPrivate::QMetaTypeInterface *) {return &Fluent_DarkMode::staticMetaObject;},
            "Fluent_DarkMode");
        QMetaType(&metaType).id();
    }
    qmlRegisterNamespaceAndRevisions(&Fluent_DarkMode::staticMetaObject, "FluentUI", 1, nullptr, &Fluent_DarkMode::staticMetaObject, nullptr);
    qmlRegisterEnum<Fluent_DarkMode::Fluent_DarkModeType>("Fluent_DarkMode::Fluent_DarkModeType");
    qmlRegisterTypesAndRevisions<WindowHelper>("FluentUI", 1);
    QT_WARNING_POP
    qmlRegisterModule("FluentUI", 1, 0);
}

static const QQmlModuleRegistration fluentUIRegistration("FluentUI", qml_register_types_FluentUI);
