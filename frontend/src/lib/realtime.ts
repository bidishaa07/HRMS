"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { API_URL } from "./api";

export type RealtimeStatus = "connected" | "connecting" | "degraded" | "offline";

const EVENT_INVALIDATIONS: Record<string, string[][]> = {
  LEAVE_REQUESTED: [["leaves"], ["notifications"]],
  LEAVE_APPROVED: [["leaves"], ["notifications"]],
  LEAVE_REJECTED: [["leaves"], ["notifications"]],
  EMPLOYEE_CREATED: [["employees"], ["dashboard-summary"]],
  EMPLOYEE_UPDATED: [["employees"], ["dashboard-summary"]],
  EMPLOYEE_DEACTIVATED: [["employees"], ["dashboard-summary"]],
  ATTENDANCE_MARKED: [["attendance"], ["dashboard-summary"], ["analytics"]],
  ATTENDANCE_UPDATED: [["attendance"], ["dashboard-summary"], ["analytics"]],
};

function websocketUrl() {
  return `${API_URL.replace(/^http/, "ws")}/realtime/ws`;
}

export function useRealtime() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<RealtimeStatus>("connecting");

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;
    let retryCount = 0;
    const seen = new Set<string>();

    const invalidate = (eventType?: string) => {
      const queryKeys = eventType
        ? EVENT_INVALIDATIONS[eventType] ?? []
        : [["leaves"], ["notifications"], ["employees"], ["attendance"], ["dashboard-summary"], ["analytics"]];
      for (const queryKey of queryKeys) {
        void queryClient.invalidateQueries({ queryKey });
      }
    };

    const connect = () => {
      if (stopped) return;
      setStatus(retryCount ? "degraded" : "connecting");
      socket = new WebSocket(websocketUrl());
      socket.onopen = () => {
        retryCount = 0;
        setStatus("connected");
        socket?.send("READY");
      };
      socket.onmessage = (message) => {
        try {
          const envelope = JSON.parse(message.data) as {
            type?: string;
            event?: { event_id?: string; event_type?: string; schema_version?: number };
          };
          if (envelope.type !== "EVENT" || !envelope.event || envelope.event.schema_version !== 1) return;
          const eventId = envelope.event.event_id;
          if (!eventId || seen.has(eventId)) return;
          seen.add(eventId);
          if (seen.size > 500) seen.delete(seen.values().next().value as string);
          if (envelope.event.event_type && EVENT_INVALIDATIONS[envelope.event.event_type]) invalidate(envelope.event.event_type);
        } catch {
          // Ignore malformed events; the next reconnect will perform an authoritative refetch.
        }
      };
      socket.onclose = () => {
        if (stopped) return;
        setStatus("degraded");
        invalidate();
        retryCount += 1;
        const delay = Math.min(10_000, 500 * 2 ** Math.min(retryCount - 1, 4));
        retryTimer = setTimeout(connect, delay);
      };
      socket.onerror = () => setStatus("degraded");
    };

    const handleOffline = () => setStatus("offline");
    const handleOnline = () => {
      if (!socket || socket.readyState === WebSocket.CLOSED) connect();
    };
    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);
    connect();
    return () => {
      stopped = true;
      if (retryTimer) clearTimeout(retryTimer);
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
      socket?.close();
    };
  }, [queryClient]);

  return status;
}

export const useLeaveRealtime = useRealtime;
