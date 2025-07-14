Feature: DNS Connectivity From scale-test Deployment

  Scenario: Ping configured DNS IP from scale-test pod
    Given a running deployment named "scale-test" in namespace "platform-scale-test"
    And at least one pod from the deployment is running
    When I ping the configured DNS IP from that pod
    Then the ping should succeed with 0% packet loss
