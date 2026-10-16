package com.costpilot.guardian;

import com.google.adk.events.Event;
import com.google.adk.runner.InMemoryRunner;
import com.google.adk.sessions.Session;
import com.google.genai.types.Content;
import com.google.genai.types.Part;
import io.reactivex.rxjava3.core.Flowable;
import java.util.Scanner;

/** Chat with the agent in a terminal:  mvn compile exec:java */
public final class ConsoleRunner {

    public static void main(String[] args) {
        InMemoryRunner runner = new InMemoryRunner(BudgetGuardianAgent.ROOT_AGENT);
        Session session = runner.sessionService().createSession(BudgetGuardianAgent.NAME, "lab-user").blockingGet();
        try (Scanner in = new Scanner(System.in)) {
            while (true) {
                System.out.print("\nYou > ");
                if (!in.hasNextLine()) {
                    return;
                }
                String text = in.nextLine();
                if (text.isBlank() || "quit".equalsIgnoreCase(text)) {
                    return;
                }
                Flowable<Event> events = runner.runAsync("lab-user", session.id(),
                        Content.fromParts(Part.fromText(text)));
                events.blockingForEach(event -> System.out.println(event.stringifyContent()));
            }
        }
    }
}
