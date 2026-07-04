"use client";

import { useEffect, useState } from "react";
import { Building2, Loader2, Users } from "lucide-react";
import { api, type Department } from "@/lib/api";
import { Modal } from "../modal";
import { Card } from "../ui";

export function OrganizationView() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDepartment, setSelectedDepartment] = useState<Department | null>(null);

  useEffect(() => {
    api.departments().then(setDepartments).finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-5">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[.16em] text-violet-600">
          Company structure
        </p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight">Organization</h2>
        <p className="mt-1 text-xs text-[#858c97]">
          Departments, reporting structure, and team distribution.
        </p>
      </div>

      {loading ? (
        <div className="grid h-48 place-items-center">
          <Loader2 className="animate-spin text-violet-600" />
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {departments.map((department) => (
            <button
              key={department.id}
              type="button"
              onClick={() => setSelectedDepartment(department)}
              className="text-left"
            >
              <Card className="p-5">
                <div className="flex items-start justify-between">
                  <div className="grid size-10 place-items-center rounded-xl bg-violet-100 text-violet-700">
                    <Building2 size={17} />
                  </div>
                  <span className="mono text-[10px] text-[#9298a1]">
                    {department.employees} people
                  </span>
                </div>
                <h3 className="mt-4 text-sm font-semibold">{department.name}</h3>
                <p className="mt-1 text-[10px] leading-5 text-[#858c97]">
                  {department.description}
                </p>
                <div className="mt-4 flex items-center gap-2 border-t border-black/[.05] pt-3 text-[10px] text-[#6f7681]">
                  <Users size={12} />
                  {department.employees ? "Active team" : "No assigned employees"}
                </div>
              </Card>
            </button>
          ))}
        </div>
      )}

      <Modal
        open={Boolean(selectedDepartment)}
        onClose={() => setSelectedDepartment(null)}
        title={selectedDepartment?.name ?? "Department details"}
        description="Team composition and staffing summary."
      >
        {selectedDepartment && (
          <div className="space-y-3 text-sm text-[#515763]">
            <div className="rounded-2xl bg-violet-50 p-4">
              <p className="text-xs uppercase tracking-[.2em] text-violet-600">
                Department overview
              </p>
              <p className="mt-2 font-semibold text-[#17191f]">
                {selectedDepartment.description || "No description provided."}
              </p>
            </div>
            <div className="rounded-2xl border border-black/[.05] p-4">
              <p className="text-[10px] uppercase tracking-[.2em] text-[#9298a1]">
                Assigned employees
              </p>
              <p className="mt-2 text-2xl font-semibold text-[#17191f]">
                {selectedDepartment.employees}
              </p>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
