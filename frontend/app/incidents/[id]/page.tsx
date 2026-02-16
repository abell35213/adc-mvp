import IncidentDetailClient from "./IncidentDetailClient";

export async function generateStaticParams() {
  return [{ id: "placeholder" }];
}

export default function IncidentDetailPage() {
  return <IncidentDetailClient />;
}
