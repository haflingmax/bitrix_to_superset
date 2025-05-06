import React, { useState, useEffect } from "react";
import axios, { AxiosError } from "axios";
import StatusCard from "./components/StatusCard";
import { FaSyncAlt, FaMoon, FaSun, FaTrashAlt, FaStop } from "react-icons/fa";
import { ServiceStatus } from "./types";
import log from "loglevel";
log.setLevel("error");

const SunIcon = FaSun as React.FC<React.SVGProps<SVGSVGElement>>;
const MoonIcon = FaMoon as React.FC<React.SVGProps<SVGSVGElement>>;
const SyncIcon = FaSyncAlt as React.FC<React.SVGProps<SVGSVGElement>>;
const TrashIcon = FaTrashAlt as React.FC<React.SVGProps<SVGSVGElement>>;
const StopIcon = FaStop as React.FC<React.SVGProps<SVGSVGElement>>;

interface SyncCounts {
  bitrix: number;
  db: number;
}

interface SyncStatus {
  running: boolean;
  progress: number;
  total: number;
  last_run: string | null;
  stop_requested: boolean;
}

// Настраиваем базовый URL для axios
const backendHost = process.env.REACT_APP_BACKEND_HOST || "localhost"; // По умолчанию localhost
const backendPort = process.env.REACT_APP_BACKEND_PORT || "5000"; // По умолчанию 5000
const baseURL = `http://${backendHost}:${backendPort}`;
const apiClient = axios.create({
  baseURL,
  timeout: 60000,
});

const App: React.FC = () => {
  const [status, setStatus] = useState<ServiceStatus>({
    backend: { status: "unknown" },
    bitrix24: { available: false, license: "N/A", scopes: [] },
  });
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [syncCounts, setSyncCounts] = useState<{ [key: string]: SyncCounts }>({});
  const [syncStatus, setSyncStatus] = useState<{ [key: string]: SyncStatus }>({});
  const [syncPrompt, setSyncPrompt] = useState<string | null>(null);
  const [clearPrompt, setClearPrompt] = useState<string | null>(null);

  const syncTables = [
    { name: "Deals", method: "crm.deal.get", entity: "deals" },
    { name: "Tasks", method: "tasks.task.get", entity: "tasks" },
    { name: "Projects", method: "sonet_group.get", entity: "projects" },
  ];

  const fetchStatus = async () => {
    try {
      const response = await apiClient.get<ServiceStatus>("/status");
      setStatus({
        backend: { status: response.data.backend.status },
        bitrix24: { ...response.data.bitrix24 },
      });
    } catch (err) {
      const error = err as AxiosError;
      const errorMessage = error.message || "Сервис недоступен";
      setStatus((prev) => ({
        backend: { status: "down", error: errorMessage },
        bitrix24: { ...prev.bitrix24, error: errorMessage },
      }));
    }
  };

  const fetchSyncCounts = async () => {
    try {
      const response = await apiClient.get<{ [key: string]: SyncCounts }>("/sync_counts");
      setSyncCounts(response.data);
    } catch (err) {
      log.error("Failed to fetch sync counts:", err);
    }
  };

  const fetchSyncStatus = async () => {
    try {
      const response = await apiClient.get<{ [key: string]: SyncStatus }>("/sync_status");
      setSyncStatus(response.data);
    } catch (err) {
      log.error("Failed to fetch sync status:", err);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchSyncCounts();
    fetchSyncStatus();

    const interval = setInterval(() => {
      fetchStatus();
      fetchSyncCounts();
      fetchSyncStatus();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const toggleDarkMode = () => {
    setIsDarkMode((prev) => !prev);
    document.documentElement.classList.toggle("dark");
  };

  const handleSync = (entity: string) => {
    const counts = syncCounts[entity];
    if (!counts) return;

    if (counts.bitrix === counts.db) {
      alert(`Синхронизация для ${entity} не требуется: Bitrix (${counts.bitrix}) = DB (${counts.db})`);
    } else {
      setSyncPrompt(entity);
    }
  };

  const confirmSync = async () => {
    if (!syncPrompt) return;
    try {
      await apiClient.post(`/sync/${syncPrompt}`);
      setSyncPrompt(null);
    } catch (err) {
      log.error("Failed to start sync:", err);
    }
  };

  const handleStopSync = async (entity: string) => {
    try {
      await apiClient.post(`/stop_sync/${entity}`);
      log.info(`Requested to stop sync for ${entity}`);
    } catch (err) {
      log.error("Failed to stop sync:", err);
    }
  };

  const handleClear = (entity: string) => {
    setClearPrompt(entity);
  };

  const confirmClear = async () => {
    if (!clearPrompt) return;
    try {
      await apiClient.post(`/clear/${clearPrompt}`);
      setClearPrompt(null);
      fetchSyncCounts();
    } catch (err) {
      log.error("Failed to clear table:", err);
    }
  };

  const getProgressPercentage = (progress: number, total: number) => {
    return total > 0 ? Math.min((progress / total) * 100, 100) : 0;
  };

  return (
    <div className={`flex flex-col min-h-screen ${isDarkMode ? "dark bg-gray-900" : "bg-gray-100"}`}>
      <header className="bg-white dark:bg-gray-800 shadow-md p-4 flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100">Мониторинг сервисов</h1>
        <button
          onClick={toggleDarkMode}
          className="p-2 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-100 hover:bg-gray-300 dark:hover:bg-gray-600"
        >
          {isDarkMode ? <SunIcon className="w-5 h-5" /> : <MoonIcon className="w-5 h-5" />}
        </button>
      </header>

      <main className="flex flex-col items-center justify-center p-6 flex-grow">
        <div className="flex flex-col md:flex-row gap-6 mb-8">
          <StatusCard
            title="Бэкенд"
            isAvailable={status.backend.status === "running"}
            details={{
              status: status.backend.status === "running" ? "Работает" : "Не работает",
              error: status.backend.error || "",
            }}
            icon="server"
          />
          <StatusCard
            title="Bitrix24"
            isAvailable={status.bitrix24.available}
            details={{
              license: status.bitrix24.license,
              scopes: status.bitrix24.scopes,
              error: status.bitrix24.error || "",
            }}
            icon="cloud"
          />
        </div>

        <div className="w-full max-w-2xl">
          <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-100 mb-4">
            Синхронизация таблиц
          </h2>
          <div className="bg-white dark:bg-gray-800 shadow-lg rounded-xl p-6">
            {syncTables.map((table) => (
              <div
                key={table.name}
                className="flex flex-col py-3 border-b last:border-b-0 border-gray-200 dark:border-gray-700"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-800 dark:text-gray-100 font-medium">{table.name}</p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">{table.method}</p>
                    {syncCounts[table.entity] && (
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        Bitrix: {syncCounts[table.entity].bitrix}, DB: {syncCounts[table.entity].db}
                      </p>
                    )}
                    {syncStatus[table.entity]?.running && (
                      <p className="text-sm text-blue-500">
                        Синхронизация: {syncStatus[table.entity].progress} / {syncStatus[table.entity].total}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleSync(table.entity)}
                      disabled={syncStatus[table.entity]?.running}
                      className={`flex items-center px-3 py-1 rounded-lg shadow transition-colors ${
                        syncStatus[table.entity]?.running
                          ? "bg-gray-400 text-gray-700 cursor-not-allowed"
                          : "bg-green-500 text-white hover:bg-green-600"
                      }`}
                    >
                      <SyncIcon className="w-4 h-4 mr-2" /> Синхронизировать
                    </button>
                    {syncStatus[table.entity]?.running && (
                      <button
                        onClick={() => handleStopSync(table.entity)}
                        className="flex items-center px-3 py-1 rounded-lg shadow bg-orange-500 text-white hover:bg-orange-600 transition-colors"
                      >
                        <StopIcon className="w-4 h-4 mr-2" /> Остановить
                      </button>
                    )}
                    <button
                      onClick={() => handleClear(table.entity)}
                      disabled={syncStatus[table.entity]?.running}
                      className={`flex items-center px-3 py-1 rounded-lg shadow transition-colors ${
                        syncStatus[table.entity]?.running
                          ? "bg-gray-400 text-gray-700 cursor-not-allowed"
                          : "bg-red-500 text-white hover:bg-red-600"
                      }`}
                    >
                      <TrashIcon className="w-4 h-4 mr-2" /> Очистить
                    </button>
                  </div>
                </div>
                {syncStatus[table.entity]?.running && (
                  <div className="mt-2">
                    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
                      <div
                        className="bg-blue-500 h-2.5 rounded-full transition-all duration-500"
                        style={{
                          width: `${getProgressPercentage(
                            syncStatus[table.entity].progress,
                            syncStatus[table.entity].total
                          )}%`,
                        }}
                      ></div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {syncPrompt && (
          <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50">
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg">
              <p className="text-gray-800 dark:text-gray-100">
                Количество в Bitrix: {syncCounts[syncPrompt].bitrix}, в базе: {syncCounts[syncPrompt].db}.
                Синхронизировать?
              </p>
              <div className="mt-4 flex justify-end gap-4">
                <button
                  onClick={() => setSyncPrompt(null)}
                  className="px-4 py-2 bg-gray-300 text-gray-800 rounded-lg hover:bg-gray-400"
                >
                  Отмена
                </button>
                <button
                  onClick={confirmSync}
                  className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
                >
                  Да
                </button>
              </div>
            </div>
          </div>
        )}

        {clearPrompt && (
          <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50">
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg">
              <p className="text-gray-800 dark:text-gray-100">
                Вы уверены, что хотите очистить таблицу {clearPrompt}?
              </p>
              <div className="mt-4 flex justify-end gap-4">
                <button
                  onClick={() => setClearPrompt(null)}
                  className="px-4 py-2 bg-gray-300 text-gray-800 rounded-lg hover:bg-gray-400"
                >
                  Отмена
                </button>
                <button
                  onClick={confirmClear}
                  className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600"
                >
                  Да
                </button>
              </div>
            </div>
          </div>
        )}

        <button
          onClick={fetchStatus}
          className="mt-6 flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg shadow hover:bg-blue-600"
        >
          <SyncIcon className="w-4 h-4 mr-2" /> Обновить статус
        </button>
      </main>

      <footer className="bg-white dark:bg-gray-800 p-4 text-center text-gray-600 dark:text-gray-300 shadow-inner">
        © 2025 Мониторинг сервисов | Версия 1.0.0
      </footer>
    </div>
  );
};

export default App;