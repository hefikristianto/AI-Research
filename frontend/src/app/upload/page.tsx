"use client";

import DashboardLayout from "@/components/layout/DashboardLayout";
import UploadZone from "@/components/upload/UploadZone";

export default function UploadPage() {

    return (

        <DashboardLayout>

            <div className="mx-auto max-w-5xl">

                <div className="mb-8">

                    <h1 className="text-4xl font-bold text-white">
                        Upload Chart
                    </h1>

                    <p className="mt-2 text-neutral-400">
                        Upload screenshot TradingView, MT5, cTrader, atau platform trading lainnya.
                    </p>

                </div>

                <UploadZone />

            </div>

        </DashboardLayout>

    );

}
