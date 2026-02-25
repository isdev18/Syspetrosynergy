import { google } from "googleapis";

function parseServiceAccount() {
  if (process.env.GOOGLE_SERVICE_ACCOUNT_JSON) {
    return JSON.parse(process.env.GOOGLE_SERVICE_ACCOUNT_JSON);
  }

  if (process.env.GOOGLE_SERVICE_ACCOUNT_JSON_BASE64) {
    const decoded = Buffer.from(process.env.GOOGLE_SERVICE_ACCOUNT_JSON_BASE64, "base64").toString("utf8");
    return JSON.parse(decoded);
  }

  return null;
}

async function getSheetsClient() {
  const creds = parseServiceAccount();
  if (!creds) {
    throw new Error("Credenciais Google nao configuradas");
  }

  const auth = new google.auth.GoogleAuth({
    credentials: creds,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });

  const client = await auth.getClient();
  return google.sheets({ version: "v4", auth: client });
}

export async function appendMedicao({ tanque, payload, operador }) {
  const spreadsheetId = process.env.GOOGLE_SHEETS_SPREADSHEET_ID;
  if (!spreadsheetId) {
    throw new Error("GOOGLE_SHEETS_SPREADSHEET_ID nao configurado");
  }

  const tabName = tanque.sheet_tab || process.env.DEFAULT_REGISTROS_TAB || "Registros";
  const now = new Date();
  const data = now.toISOString().slice(0, 10);

  const row = [
    data,
    payload.hora,
    tanque.campo_nome,
    tanque.tanque_nome,
    String(payload.medida),
    payload.situacao,
    payload.observacao || "",
    operador,
    tanque.sheet_key || "",
  ];

  const sheets = await getSheetsClient();
  await sheets.spreadsheets.values.append({
    spreadsheetId,
    range: `${tabName}!A:I`,
    valueInputOption: "USER_ENTERED",
    insertDataOption: "INSERT_ROWS",
    requestBody: { values: [row] },
  });
}
