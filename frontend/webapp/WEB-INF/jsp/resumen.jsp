<%--
  Resumen ejecutivo - VISTA TEMPORAL del bloque de login (Sprint 3).
  Comprueba sesion, rol y cierre de sesion. Se reemplaza por la vista completa
  (Estado de la cadena, Que atender hoy, Demanda y pronostico; CC-10).
--%>
<%@ page contentType="text/html; charset=UTF-8" pageEncoding="UTF-8" %>
<%@ taglib prefix="sc" uri="/WEB-INF/sc.tld" %>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="csrf-token" content="${sc:esc(usuario.csrf)}">
    <title>Resumen ejecutivo · Supply Chain</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700&display=swap">
    <link rel="stylesheet" href="${pageContext.request.contextPath}/css/app.css">
</head>
<body class="pagina-app">
<aside class="menu">
    <div class="menu-marca">
        <span class="marca-titulo">SUPPLY CHAIN</span>
        <span class="marca-sub">PluriOne · Dashboard ejecutivo</span>
    </div>
    <nav class="menu-enlaces" aria-label="Módulos">
        <a class="activo" href="${pageContext.request.contextPath}/resumen" aria-current="page">Resumen ejecutivo</a>
    </nav>
    <div class="menu-usuario">
        <span class="menu-usuario-nombre">${sc:esc(usuario.nombre)}</span>
        <span class="menu-usuario-rol">Rol: ${sc:esc(usuario.rolVisible)}</span>
        <form method="post" action="${pageContext.request.contextPath}/logout">
            <input type="hidden" name="_csrf" value="${sc:esc(usuario.csrf)}">
            <button type="submit" class="boton boton-secundario">Cerrar sesión</button>
        </form>
    </div>
</aside>
<main class="contenido">
    <h1 class="titulo-vista">Resumen ejecutivo</h1>
    <p class="aviso aviso-info">Sesión iniciada como ${sc:esc(usuario.usuario)}. El Resumen ejecutivo se conecta en el siguiente bloque.</p>
</main>
</body>
</html>