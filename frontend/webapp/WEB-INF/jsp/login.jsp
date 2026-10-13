<%-- Inicio de sesion (CC-20). Todo dato variable pasa por sc:esc (prevencion de XSS). --%>
<%@ page contentType="text/html; charset=UTF-8" pageEncoding="UTF-8" %>
<%@ taglib prefix="sc" uri="/WEB-INF/sc.tld" %>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Iniciar sesión · Supply Chain</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700&display=swap">
    <link rel="stylesheet" href="${pageContext.request.contextPath}/css/app.css">
</head>
<body class="pagina-login">
<main class="login">
    <header class="login-marca">
        <span class="marca-titulo">SUPPLY CHAIN</span>
        <span class="marca-sub">PluriOne · Dashboard ejecutivo</span>
    </header>

    <h1 class="login-titulo">Iniciar sesión</h1>

    <p class="aviso aviso-info" role="status" ${empty aviso ? 'hidden' : ''}>${sc:esc(aviso)}</p>
    <p class="aviso aviso-error" role="alert" ${empty error ? 'hidden' : ''}>${sc:esc(error)}</p>

    <form class="login-form" method="post" action="${pageContext.request.contextPath}/login" novalidate>
        <input type="hidden" name="_csrf" value="${sc:esc(csrf)}">

        <label for="usuario">Usuario</label>
        <input id="usuario" name="usuario" type="text" maxlength="60" required
               autocomplete="username" autocapitalize="none" spellcheck="false" autofocus
               value="${sc:esc(usuarioIngresado)}">

        <label for="contrasena">Contraseña</label>
        <input id="contrasena" name="contrasena" type="password" maxlength="128" required
               autocomplete="current-password">

        <button type="submit" class="boton boton-principal">Entrar</button>
    </form>

    <p class="login-nota">Los datos operativos son simulados; no provienen de un ERP real.</p>
</main>
</body>
</html>