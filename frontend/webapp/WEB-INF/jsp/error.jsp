<%-- Pagina de error generica: no muestra trazas ni detalles internos. --%>
<%@ page contentType="text/html; charset=UTF-8" pageEncoding="UTF-8" isErrorPage="true" %>
<%@ taglib prefix="sc" uri="/WEB-INF/sc.tld" %>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Página no disponible · Supply Chain</title>
    <link rel="stylesheet" href="${pageContext.request.contextPath}/css/app.css">
</head>
<body class="pagina-login">
<main class="login">
    <header class="login-marca">
        <span class="marca-titulo">SUPPLY CHAIN</span>
        <span class="marca-sub">PluriOne · Dashboard ejecutivo</span>
    </header>
    <h1 class="login-titulo">${requestScope['jakarta.servlet.error.status_code'] == 404 ? 'Página no encontrada' : 'Algo salió mal'}</h1>
    <p class="login-nota">Código ${sc:esc(requestScope['jakarta.servlet.error.status_code'])}. Si el problema continúa, avisa al administrador.</p>
    <p><a class="enlace" href="${pageContext.request.contextPath}/resumen">Volver al Resumen ejecutivo</a></p>
</main>
</body>
</html>