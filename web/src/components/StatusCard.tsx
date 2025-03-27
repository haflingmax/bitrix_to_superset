import React from "react";
import { FaServer, FaCloud } from "react-icons/fa";

// Явное приведение типов для иконок
const ServerIcon = FaServer as React.FC<React.SVGProps<SVGSVGElement>>;
const CloudIcon = FaCloud as React.FC<React.SVGProps<SVGSVGElement>>;

interface StatusCardProps {
  title: string;
  isAvailable: boolean;
  details: { [key: string]: string | string[] };
  icon: "server" | "cloud";
}

const StatusCard: React.FC<StatusCardProps> = ({ title, isAvailable, details, icon }) => {
  return (
    <div className="bg-white dark:bg-gray-800 shadow-lg rounded-xl p-6 w-full max-w-md transition-all transform hover:scale-105 animate-fade-in">
      <div className="flex items-center mb-4">
        {icon === "server" ? (
          <ServerIcon className={`text-3xl ${isAvailable ? "text-green-500" : "text-red-500"} mr-3`} />
        ) : (
          <CloudIcon className={`text-3xl ${isAvailable ? "text-green-500" : "text-red-500"} mr-3`} />
        )}
        <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-100">{title}</h2>
      </div>
      <p className={isAvailable ? "text-green-500 font-bold" : "text-red-500 font-bold"}>
        Статус: {isAvailable ? "Доступен" : "Недоступен"}
      </p>
      {Object.entries(details).map(([key, value]) => (
        <p key={key} className="mt-2">
          {key === "error" && value ? ( // Показываем "Ошибка:" только если value не пустое
            <span className="text-red-600 dark:text-red-400">
              Ошибка: <span className="text-red-800 dark:text-red-200">{value}</span>
            </span>
          ) : key !== "error" ? ( // Пропускаем пустой error
            <>
              <span className="text-gray-600 dark:text-gray-300">
                {key.charAt(0).toUpperCase() + key.slice(1)}:{" "}
              </span>
              <span
                className={
                  key === "status" && !isAvailable
                    ? "text-red-500"
                    : "text-gray-800 dark:text-gray-100"
                }
              >
                {Array.isArray(value) ? value.join(", ") : value}
              </span>
            </>
          ) : null}
        </p>
      ))}
    </div>
  );
};

export default StatusCard;