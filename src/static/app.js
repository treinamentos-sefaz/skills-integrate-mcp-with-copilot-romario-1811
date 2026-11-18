document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const messageDiv = document.getElementById("message");
  const loginToggle = document.getElementById("login-toggle");
  const loginForm = document.getElementById("login-form");
  const logoutButton = document.getElementById("logout-button");
  const authStatus = document.getElementById("auth-status");
  const adminRequired = document.getElementById("admin-required");
  let isAdmin = false;

  function setAdminStatus(authenticated, configured = true) {
    isAdmin = authenticated;
    signupForm.classList.toggle("hidden", !isAdmin);
    adminRequired.classList.toggle("hidden", isAdmin);
    loginToggle.classList.toggle("hidden", isAdmin);
    logoutButton.classList.toggle("hidden", !isAdmin);
    loginForm.classList.add("hidden");

    if (isAdmin) {
      authStatus.textContent = "Signed in as a teacher.";
    } else if (!configured) {
      authStatus.textContent = "Teacher login is not configured.";
    } else {
      authStatus.textContent = "Viewing activities as a student.";
    }
  }

  async function refreshAuthStatus() {
    const response = await fetch("/auth/status");
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail || "Unable to check teacher login.");
    }
    setAdminStatus(result.authenticated, result.configured);
  }

  // Function to fetch activities from API
  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      if (!response.ok) {
        throw new Error("Failed to load activities.");
      }
      const activities = await response.json();

      activitiesList.replaceChildren();
      activitySelect.replaceChildren(new Option("-- Select an activity --", ""));

      // Populate activities list
      Object.entries(activities).forEach(([name, details]) => {
        const activityCard = document.createElement("div");
        activityCard.className = "activity-card";

        const spotsLeft =
          details.max_participants - details.participants.length;

        const title = document.createElement("h4");
        title.textContent = name;
        activityCard.appendChild(title);

        const description = document.createElement("p");
        description.textContent = details.description;
        activityCard.appendChild(description);

        const schedule = document.createElement("p");
        const scheduleLabel = document.createElement("strong");
        scheduleLabel.textContent = "Schedule: ";
        schedule.append(scheduleLabel, document.createTextNode(details.schedule));
        activityCard.appendChild(schedule);

        const availability = document.createElement("p");
        const availabilityLabel = document.createElement("strong");
        availabilityLabel.textContent = "Availability: ";
        availability.append(
          availabilityLabel,
          document.createTextNode(`${spotsLeft} spots left`)
        );
        activityCard.appendChild(availability);

        const participantsContainer = document.createElement("div");
        participantsContainer.className = "participants-container";
        const participantsSection = document.createElement("div");
        participantsSection.className = "participants-section";
        const participantsHeading = document.createElement("h5");
        participantsHeading.textContent = "Participants:";
        participantsSection.appendChild(participantsHeading);

        if (details.participants.length > 0) {
          const participantsList = document.createElement("ul");
          participantsList.className = "participants-list";
          details.participants.forEach((email) => {
            const participant = document.createElement("li");
            const participantEmail = document.createElement("span");
            participantEmail.className = "participant-email";
            participantEmail.textContent = email;
            participant.appendChild(participantEmail);

            if (isAdmin) {
              const deleteButton = document.createElement("button");
              deleteButton.type = "button";
              deleteButton.className = "delete-btn";
              deleteButton.textContent = "Remove";
              deleteButton.addEventListener("click", () =>
                handleUnregister(name, email)
              );
              participant.appendChild(deleteButton);
            }

            participantsList.appendChild(participant);
          });
          participantsSection.appendChild(participantsList);
        } else {
          const emptyMessage = document.createElement("p");
          emptyMessage.textContent = "No participants yet";
          participantsSection.appendChild(emptyMessage);
        }

        participantsContainer.appendChild(participantsSection);
        activityCard.appendChild(participantsContainer);

        activitiesList.appendChild(activityCard);

        // Add option to select dropdown
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        activitySelect.appendChild(option);
      });
    } catch (error) {
      activitiesList.innerHTML =
        "<p>Failed to load activities. Please try again later.</p>";
      console.error("Error fetching activities:", error);
    }
  }

  // Handle unregister functionality
  async function handleUnregister(activity, email) {
    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(
          activity
        )}/unregister?email=${encodeURIComponent(email)}`,
        {
          method: "DELETE",
        }
      );

      const result = await response.json();

      if (response.ok) {
        messageDiv.textContent = result.message;
        messageDiv.className = "success";

        // Refresh activities list to show updated participants
        fetchActivities();
      } else {
        messageDiv.textContent = result.detail || "An error occurred";
        messageDiv.className = "error";
      }

      messageDiv.classList.remove("hidden");

      // Hide message after 5 seconds
      setTimeout(() => {
        messageDiv.classList.add("hidden");
      }, 5000);
    } catch (error) {
      messageDiv.textContent = "Failed to unregister. Please try again.";
      messageDiv.className = "error";
      messageDiv.classList.remove("hidden");
      console.error("Error unregistering:", error);
    }
  }

  loginToggle.addEventListener("click", () => {
    loginForm.classList.toggle("hidden");
    if (!loginForm.classList.contains("hidden")) {
      document.getElementById("username").focus();
    }
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(loginForm);

    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.fromEntries(formData.entries())),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || "Login failed.");
      }

      await refreshAuthStatus();
      await fetchActivities();
      authStatus.textContent = result.message;
      loginForm.reset();
    } catch (error) {
      authStatus.textContent = `Login failed: ${error.message}`;
      console.error("Error logging in:", error);
    }
  });

  logoutButton.addEventListener("click", async () => {
    try {
      const response = await fetch("/auth/logout", { method: "POST" });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || "Logout failed.");
      }
      setAdminStatus(false);
      await fetchActivities();
      authStatus.textContent = result.message;
    } catch (error) {
      authStatus.textContent = `Logout failed: ${error.message}`;
      console.error("Error logging out:", error);
    }
  });

  // Handle form submission
  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("email").value;
    const activity = document.getElementById("activity").value;

    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(
          activity
        )}/signup?email=${encodeURIComponent(email)}`,
        {
          method: "POST",
        }
      );

      const result = await response.json();

      if (response.ok) {
        messageDiv.textContent = result.message;
        messageDiv.className = "success";
        signupForm.reset();

        // Refresh activities list to show updated participants
        fetchActivities();
      } else {
        messageDiv.textContent = result.detail || "An error occurred";
        messageDiv.className = "error";
      }

      messageDiv.classList.remove("hidden");

      // Hide message after 5 seconds
      setTimeout(() => {
        messageDiv.classList.add("hidden");
      }, 5000);
    } catch (error) {
      messageDiv.textContent = "Failed to sign up. Please try again.";
      messageDiv.className = "error";
      messageDiv.classList.remove("hidden");
      console.error("Error signing up:", error);
    }
  });

  // Initialize app
  refreshAuthStatus()
    .catch((error) => {
      setAdminStatus(false, false);
      authStatus.textContent = `Teacher login unavailable: ${error.message}`;
      console.error("Error checking teacher login:", error);
    })
    .finally(fetchActivities);
});
