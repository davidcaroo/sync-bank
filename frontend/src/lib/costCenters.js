// Alegra marks cost centers as active/inactive; a missing status counts as active.
export const isActiveCostCenter = (costCenter) =>
  String(costCenter?.status || 'active').toLowerCase() === 'active'

export const activeCostCenters = (costCenters) =>
  (costCenters || []).filter(isActiveCostCenter)
