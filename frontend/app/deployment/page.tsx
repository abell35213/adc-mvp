import MainLayout from "@/components/MainLayout";
import DeploymentCoverageCard from "@/components/commercial/DeploymentCoverageCard";
import ExpansionReadinessBanner from "@/components/commercial/ExpansionReadinessBanner";

export default function DeploymentPage() {
  return (
    <MainLayout title="Deployment Coverage">
      <div className="space-y-4">
        <ExpansionReadinessBanner readyMarkets={5} blockedMarkets={2} />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <DeploymentCoverageCard region="US West" coveragePercent={94} gapCount={2} />
          <DeploymentCoverageCard region="US Central" coveragePercent={90} gapCount={3} />
          <DeploymentCoverageCard region="US East" coveragePercent={96} gapCount={1} />
          <DeploymentCoverageCard region="Canada" coveragePercent={82} gapCount={5} />
        </div>
      </div>
    </MainLayout>
  );
}
