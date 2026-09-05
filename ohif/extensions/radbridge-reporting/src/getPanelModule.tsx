import React from 'react';
import RadBridgeReportingPanel from './RadBridgeReportingPanel';

export default function getPanelModule({
  servicesManager,
  commandsManager,
}: withAppTypes) {

  const ReportingPanel = () => (
    <RadBridgeReportingPanel
      servicesManager={servicesManager}
      commandsManager={commandsManager}
    />
  );

  return [
    {
      name: 'reporting',
      iconName: 'clipboard',
      iconLabel: 'Report',
      label: 'RadBridge Reporting',
      component: ReportingPanel,
    },
  ];
}
