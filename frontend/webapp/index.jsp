<%@ page contentType="text/html;charset=UTF-8" language="java" %>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Dashboard Ejecutivo - Supply Chain</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">

    <nav class="navbar navbar-dark bg-dark mb-4">
        <div class="container-fluid">
            <span class="navbar-brand mb-0 h1">Dashboard Ejecutivo de Supply Chain</span>
        </div>
    </nav>

    <div class="container">

        <div class="row g-3 mb-4">
            <div class="col-md-4">
                <div class="card shadow-sm">
                    <div class="card-body text-center">
                        <h6 class="text-muted">OTIF (On Time In Full)</h6>
                        <h2 id="kpi-otif" class="fw-bold text-primary">--</h2>
                        <small id="kpi-otif-detalle" class="text-muted"></small>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card shadow-sm">
                    <div class="card-body text-center">
                        <h6 class="text-muted">Lead Time Promedio</h6>
                        <h2 id="kpi-leadtime" class="fw-bold text-primary">--</h2>
                        <small class="text-muted">días</small>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card shadow-sm">
                    <div class="card-body text-center">
                        <h6 class="text-muted">Proveedores Activos</h6>
                        <h2 id="kpi-proveedores-count" class="fw-bold text-primary">--</h2>
                        <small class="text-muted">registrados</small>
                    </div>
                </div>
            </div>
        </div>

        <div class="row g-3">
            <div class="col-md-6">
                <div class="card shadow-sm">
                    <div class="card-header">Calificación por Proveedor</div>
                    <div class="card-body">
                        <canvas id="chartProveedores"></canvas>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card shadow-sm">
                    <div class="card-header">Detalle de Proveedores</div>
                    <div class="card-body">
                        <table class="table table-sm" id="tabla-proveedores">
                            <thead>
                                <tr><th>Nombre</th><th>País</th><th>Calificación</th></tr>
                            </thead>
                            <tbody></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <p class="text-center text-muted mt-4">
            <small>Fecha del servidor (JSP): <%= new java.util.Date() %></small>
        </p>

    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <script src="js/dashboard.js"></script>
</body>
</html>