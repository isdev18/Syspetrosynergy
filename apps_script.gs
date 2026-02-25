/**
 * SysPetro - Web App para receber medicoes e gravar no Google Sheets.
 * Publicar como: Deploy > New deployment > Web app.
 * Execute as: Me
 * Who has access: Anyone
 */
var TARGET_SHEET = "BOLETIM BA";
var START_ROW = 10;

var TANK_COLUMN_MAP = {
  "TP-300-01": { hora: "B", medida: "C", sit: "E" },
  "TP-500-04": { hora: "F", medida: "G", sit: "I" },
  "TP-1000-05": { hora: "V", medida: "W", sit: "Y" },
  "TP-1000-06": { hora: "Z", medida: "AA", sit: "AC" },
  "TP-400-03": { hora: "AD", medida: "AE", sit: "AG" },
  "TP-300-03": { hora: "AT", medida: "AU", sit: "AW" },
  "TP-250-08": { hora: "AX", medida: "AY", sit: "BA" },
  "TP-300-02": { hora: "BF", medida: "BG", sit: "BI" }
};

function doGet() {
  return jsonOut({ ok: true, service: "SysPetro Apps Script" });
}

function doPost(e) {
  try {
    var payload = JSON.parse((e && e.postData && e.postData.contents) || "{}");

    var required = ["hora", "medida", "situacao"];
    for (var i = 0; i < required.length; i++) {
      var key = required[i];
      if (payload[key] === undefined || payload[key] === null || payload[key] === "") {
        return jsonOut({ ok: false, error: "Campo obrigatorio: " + key });
      }
    }

    var tankKey = resolveTankKey(payload);
    if (!tankKey || !TANK_COLUMN_MAP[tankKey]) {
      return jsonOut({ ok: false, error: "Tanque sem mapeamento: " + (tankKey || "(vazio)") });
    }

    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var ws = ss.getSheetByName(TARGET_SHEET);
    if (!ws) {
      return jsonOut({ ok: false, error: "Aba BOLETIM BA nao encontrada" });
    }

    var colMap = TANK_COLUMN_MAP[tankKey];
    var horaCol = colToIndex(colMap.hora);
    var medidaCol = colToIndex(colMap.medida);
    var sitCol = colToIndex(colMap.sit);
    var sitValue = normalizeSituacao(payload.situacao);

    var window = resolveBoletimWindow(ws, payload.boletim_data_ref, horaCol);
    if (!window.ok) {
      return jsonOut({ ok: false, error: window.error });
    }

    var target = resolveTargetRow(
      ws,
      horaCol,
      medidaCol,
      payload.hora,
      window.startRow,
      window.endRow
    );
    var targetRow = target.row;
    if (!targetRow) {
      return jsonOut({ ok: false, error: "Bloco do boletim sem linha disponivel para gravacao" });
    }
    if (target.isClosing) {
      sitValue = "Prod";
    }

    ws.getRange(targetRow, horaCol).setValue(payload.hora);
    ws.getRange(targetRow, medidaCol).setValue(payload.medida);
    ws.getRange(targetRow, sitCol).setValue(sitValue);

    return jsonOut({
      ok: true,
      sheet: ws.getName(),
      row: targetRow,
      boletim_start_row: window.startRow,
      boletim_end_row: window.endRow,
      tanque: tankKey,
      columns: colMap
    });
  } catch (err) {
    return jsonOut({ ok: false, error: String(err) });
  }
}

function resolveTankKey(payload) {
  var raw = String(payload.tanque_sheet_key || payload.tanque_id || payload.tanque_nome || "").toUpperCase();
  var match = raw.match(/TP-\d+-\d+/);
  return match ? match[0] : raw;
}

function findFirstEmptyRow(ws, colIndex, startRow, endRow) {
  var lastRow = Math.max(ws.getLastRow(), startRow);
  var finalRow = Math.max(startRow, Math.min(endRow || lastRow, lastRow));
  var height = Math.max(finalRow - startRow + 1, 1);
  var values = ws.getRange(startRow, colIndex, height, 1).getValues();

  for (var i = 0; i < values.length; i++) {
    if (values[i][0] === "" || values[i][0] === null) {
      return startRow + i;
    }
  }

  return null;
}

function resolveTargetRow(ws, horaCol, medidaCol, horaValue, startRow, endRow) {
  var firstEmpty = findFirstEmptyRow(ws, horaCol, startRow, endRow);
  var normalizedInputHour = normalizeHourValue(horaValue);
  if (normalizedInputHour !== "12:00") {
    return { row: firstEmpty, isClosing: false };
  }

  var lastRow = Math.max(ws.getLastRow(), startRow);
  var finalRow = Math.max(startRow, Math.min(endRow || lastRow, lastRow));
  var height = Math.max(finalRow - startRow + 1, 1);
  var horaValues = ws.getRange(startRow, horaCol, height, 1).getValues();
  var medidaValues = ws.getRange(startRow, medidaCol, height, 1).getValues();

  var rows12 = [];
  for (var i = 0; i < horaValues.length; i++) {
    if (normalizeHourValue(horaValues[i][0]) === "12:00") {
      rows12.push(startRow + i);
    }
  }
  if (rows12.length === 0) {
    return { row: firstEmpty, isClosing: false };
  }

  var first12 = rows12[0];
  var last12 = rows12[rows12.length - 1];
  if (isMeasureCellEmpty(medidaValues, first12, startRow)) {
    return { row: first12, isClosing: false };
  }
  if (last12 !== first12 && isMeasureCellEmpty(medidaValues, last12, startRow)) {
    return { row: last12, isClosing: true };
  }

  return { row: firstEmpty, isClosing: false };
}

function isMeasureCellEmpty(medidaValues, rowNumber, startRow) {
  var idx = rowNumber - startRow;
  if (idx < 0 || idx >= medidaValues.length) {
    return true;
  }
  var value = medidaValues[idx][0];
  return value === "" || value === null;
}

function resolveBoletimWindow(ws, boletimDateRef, horaCol) {
  if (!horaCol) {
    horaCol = colToIndex("B");
  }
  var dateRow = findBoletimDateRow(ws, boletimDateRef);
  if (!dateRow) {
    return { ok: false, error: "Data do boletim nao encontrada: " + boletimDateRef };
  }

  var nextDateRow = findNextBoletimDateRow(ws, dateRow);
  var sectionStart = dateRow + 1;
  var sectionEnd = nextDateRow ? (nextDateRow - 1) : ws.getLastRow();

  var initialLabelRow = findRowByLabel(ws, horaCol, sectionStart, sectionEnd, "INICIAL");
  var horaHeaderRow = findRowByLabel(ws, horaCol, sectionStart, sectionEnd, "HORA");
  var rows12 = findRowsByHour(ws, horaCol, sectionStart, sectionEnd, "12:00");
  var openingRow = rows12.length > 0 ? rows12[0] : (horaHeaderRow ? (horaHeaderRow + 1) : null);
  var closingRow = rows12.length > 0 ? rows12[rows12.length - 1] : (initialLabelRow ? (initialLabelRow - 1) : null);

  if (!openingRow || !closingRow) {
    return { ok: false, error: "Nao foi possivel localizar a janela de horas do boletim para a data: " + boletimDateRef };
  }
  if (initialLabelRow && initialLabelRow > openingRow && closingRow >= initialLabelRow) {
    closingRow = initialLabelRow - 1;
  }
  if (closingRow < openingRow) {
    return { ok: false, error: "Intervalo de linhas invalido para a data: " + boletimDateRef };
  }

  return {
    ok: true,
    startRow: openingRow,
    endRow: closingRow
  };
}

function findNextBoletimDateRow(ws, currentDateRow) {
  var lastRow = ws.getLastRow();
  if (currentDateRow >= lastRow) {
    return null;
  }

  var height = lastRow - currentDateRow;
  var values = ws.getRange(currentDateRow + 1, 2, height, 1).getValues(); // B
  for (var i = 0; i < values.length; i++) {
    var label = String(values[i][0] || "").trim().toUpperCase();
    if (label === "DATA") {
      return currentDateRow + 1 + i;
    }
  }
  return null;
}

function findRowByLabel(ws, colIndex, startRow, endRow, labelText) {
  if (endRow < startRow) {
    return null;
  }
  var height = endRow - startRow + 1;
  var values = ws.getRange(startRow, colIndex, height, 1).getValues();
  var needle = String(labelText || "").trim().toUpperCase();
  for (var i = 0; i < values.length; i++) {
    var text = String(values[i][0] || "").trim().toUpperCase();
    if (text === needle) {
      return startRow + i;
    }
  }
  return null;
}

function findRowsByHour(ws, colIndex, startRow, endRow, hourText) {
  var rows = [];
  if (endRow < startRow) {
    return rows;
  }
  var height = endRow - startRow + 1;
  var values = ws.getRange(startRow, colIndex, height, 1).getValues();
  var target = normalizeHourValue(hourText);
  for (var i = 0; i < values.length; i++) {
    if (normalizeHourValue(values[i][0]) === target) {
      rows.push(startRow + i);
    }
  }
  return rows;
}

function findBoletimDateRow(ws, boletimDateRef) {
  var targetDate = parseIsoDate(boletimDateRef);
  if (!targetDate) {
    return null;
  }

  var lastRow = ws.getLastRow();
  if (lastRow < 1) {
    return null;
  }

  var values = ws.getRange(1, 2, lastRow, 2).getValues(); // B:C
  for (var i = 0; i < values.length; i++) {
    var label = String(values[i][0] || "").trim().toUpperCase();
    if (label !== "DATA") {
      continue;
    }
    var candidate = parseSheetDateValue(values[i][1]);
    if (candidate && isSameDate(candidate, targetDate)) {
      return i + 1;
    }
  }
  return null;
}

function parseIsoDate(value) {
  var text = String(value || "").trim();
  var match = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return null;
  }
  var year = Number(match[1]);
  var month = Number(match[2]) - 1;
  var day = Number(match[3]);
  return new Date(year, month, day);
}

function parseSheetDateValue(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (Object.prototype.toString.call(value) === "[object Date]") {
    return new Date(value.getFullYear(), value.getMonth(), value.getDate());
  }
  if (typeof value === "number" && isFinite(value)) {
    // Serial de data do Sheets/Excel.
    var utcMillis = Math.round((value - 25569) * 86400 * 1000);
    var d = new Date(utcMillis);
    return new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
  }
  var text = String(value).trim();
  var br = text.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (br) {
    return new Date(Number(br[3]), Number(br[2]) - 1, Number(br[1]));
  }
  var iso = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (iso) {
    return new Date(Number(iso[1]), Number(iso[2]) - 1, Number(iso[3]));
  }
  return null;
}

function isSameDate(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function normalizeHourValue(value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  if (Object.prototype.toString.call(value) === "[object Date]") {
    var hh = String(value.getHours()).padStart(2, "0");
    var mm = String(value.getMinutes()).padStart(2, "0");
    return hh + ":" + mm;
  }
  if (typeof value === "number" && isFinite(value)) {
    var minutes = Math.round(value * 24 * 60);
    var h = Math.floor(minutes / 60) % 24;
    var m = minutes % 60;
    return String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0");
  }
  var text = String(value).trim();
  var match = text.match(/^(\d{1,2}):(\d{2})/);
  if (!match) {
    return text;
  }
  return String(Number(match[1])).padStart(2, "0") + ":" + match[2];
}

function colToIndex(col) {
  var n = 0;
  for (var i = 0; i < col.length; i++) {
    n = n * 26 + (col.charCodeAt(i) - 64);
  }
  return n;
}

function normalizeSituacao(value) {
  var v = String(value || "").toUpperCase().trim();
  var map = {
    "NORMAL": "Prod",
    "ATENCAO": "Disp",
    "CRITICO": "Disp",
    "MANUTENCAO": "Disp",
    "PARADO": "Disp"
  };
  return map[v] || value;
}

function jsonOut(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
