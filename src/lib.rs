#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DiscoveredService {
    pub service_type: String,
    pub name: String,
    pub host: String,
    pub port: u16,
}

#[derive(Debug, Default)]
pub struct NetworkDiscoveryService {
    services: Vec<DiscoveredService>,
}

impl NetworkDiscoveryService {
    pub fn new() -> Self { Self { services: Vec::new() } }
    pub fn register_service(&mut self, s_type: &str, name: &str, host: &str, port: u16) {
        self.services.push(DiscoveredService {
            service_type: s_type.into(),
            name: name.into(),
            host: host.into(),
            port,
        });
    }
    pub fn get_services_by_type(&self, s_type: &str) -> Vec<&DiscoveredService> {
        self.services.iter().filter(|s| s.service_type == s_type).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_network_discovery_service_aaa() {
        // Arrange
        let mut discovery = NetworkDiscoveryService::new();
        // Act
        discovery.register_service("_ipp._tcp", "Office Printer", "192.168.1.50", 631);
        discovery.register_service("_smb._tcp", "Media Server", "192.168.1.100", 445);
        // Assert
        let printers = discovery.get_services_by_type("_ipp._tcp");
        assert_eq!(printers.len(), 1);
        assert_eq!(printers[0].name, "Office Printer");
    }
}
